import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

# ── Constants ────────────────────────────────────────────────────────────────
API_BASE_URL = "https://api.example.com/users"
REQUEST_TIMEOUT = 3  # seconds

SCORE_POINTS_WEIGHT = 1.5
SCORE_CONTRIBUTIONS_WEIGHT = 3.0

VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
SECONDS_PER_DAY = 86_400

logger = logging.getLogger(__name__)


# ── Types ─────────────────────────────────────────────────────────────────────
class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"


class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name_only"


@dataclass(frozen=True)
class UserRecord:
    uid: int
    name: str
    email: str
    days_active: float
    status: UserStatus
    score: float


# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: dict[int, dict] = {}


def _fetch_user(uid: int) -> Optional[dict]:
    """Fetch raw user data from the API, with a simple in-memory cache."""
    if uid in _cache:
        return _cache[uid]

    try:
        resp = requests.get(f"{API_BASE_URL}/{uid}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        _cache[uid] = data
        return data
    except requests.HTTPError as exc:
        logger.warning("HTTP error fetching user %s: %s", uid, exc)
    except requests.RequestException as exc:
        logger.warning("Network error fetching user %s: %s", uid, exc)
    except ValueError as exc:
        logger.warning("Invalid JSON for user %s: %s", uid, exc)

    return None


# ── Business logic ────────────────────────────────────────────────────────────
def _compute_status(days_active: float) -> UserStatus:
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    if days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW


def _compute_score(data: dict) -> float:
    return (
        data.get("points", 0) * SCORE_POINTS_WEIGHT
        + data.get("contributions", 0) * SCORE_CONTRIBUTIONS_WEIGHT
    )


def _build_record(uid: int, data: dict) -> UserRecord:
    name = f"{data['first']} {data['last']}"
    email = data["contact"]["email"]
    days_active = (time.time() - data["created_ts"]) / SECONDS_PER_DAY

    return UserRecord(
        uid=uid,
        name=name,
        email=email,
        days_active=days_active,
        status=_compute_status(days_active),
        score=_compute_score(data),
    )


# ── Formatting ────────────────────────────────────────────────────────────────
def _format_record(record: UserRecord, fmt: ReportFormat) -> str:
    match fmt:
        case ReportFormat.SUMMARY:
            return f"{record.name} ({record.status.value}) - Score: {record.score:.0f}"
        case ReportFormat.DETAIL:
            return (
                f"{record.name} <{record.email}> | "
                f"Status: {record.status.value} | "
                f"Days: {record.days_active:.0f} | "
                f"Score: {record.score:.0f}"
            )
        case ReportFormat.NAME_ONLY:
            return record.name


# ── Public API ────────────────────────────────────────────────────────────────
def get_user_report(
    user_ids: list[int],
    report_format: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """
    Fetch user data for the given IDs and return a formatted report string.
    Users that cannot be fetched are skipped and logged as warnings.
    """
    lines: list[str] = []

    for uid in user_ids:
        data = _fetch_user(uid)
        if data is None:
            continue  # already logged inside _fetch_user

        try:
            record = _build_record(uid, data)
        except KeyError as exc:
            logger.warning("Missing field for user %s: %s", uid, exc)
            continue

        lines.append(_format_record(record, report_format))

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    body = "\n".join(lines) if lines else "(no results)"
    return f"{header}\n{body}"