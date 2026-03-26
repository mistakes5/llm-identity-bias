import time
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import requests

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT_SECONDS = 3
SECONDS_PER_DAY = 86_400

VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
SCORE_POINTS_MULTIPLIER = 1.5
SCORE_CONTRIBUTIONS_MULTIPLIER = 3.0


# ── Domain types ───────────────────────────────────────────────────────────────

class ReportFormat(str, Enum):
    SUMMARY  = "summary"
    DETAIL   = "detail"
    NAME_ONLY = "name"


class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW     = "new"


@dataclass(frozen=True)
class UserRecord:
    name:        str
    email:       str
    days_active: float
    status:      UserStatus
    score:       float


# ── Cache ──────────────────────────────────────────────────────────────────────
_user_cache: dict[int, dict] = {}


def clear_cache() -> None:
    """Evict all cached user data (useful in tests or on forced refresh)."""
    _user_cache.clear()


# ── Private helpers ────────────────────────────────────────────────────────────

def _fetch_user(user_id: int) -> dict | None:
    """Return raw API data for *user_id*, reading from cache when available."""
    if user_id in _user_cache:
        return _user_cache[user_id]

    url = f"{API_BASE_URL}/users/{user_id}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()          # raises HTTPError on 4xx/5xx
        data: dict = resp.json()         # avoids the json.loads(resp.text) roundtrip
    except requests.RequestException as exc:
        logger.warning("Failed to fetch user %d: %s", user_id, exc)
        return None

    # TODO: implement cache eviction before storing (see contribution request below)
    _user_cache[user_id] = data
    return data


def _classify_status(days_active: float) -> UserStatus:
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    if days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW


def _parse_record(uid: int, data: dict) -> UserRecord | None:
    """Build a typed UserRecord from raw API data; returns None on schema mismatch."""
    try:
        name        = f"{data['first']} {data['last']}"
        email       = data["contact"]["email"]
        days_active = (time.time() - data["created_ts"]) / SECONDS_PER_DAY
        score       = (
            data["points"]        * SCORE_POINTS_MULTIPLIER
            + data["contributions"] * SCORE_CONTRIBUTIONS_MULTIPLIER
        )
    except KeyError as exc:
        logger.warning("User %d: unexpected data shape — missing key %s", uid, exc)
        return None

    return UserRecord(
        name=name,
        email=email,
        days_active=days_active,
        status=_classify_status(days_active),
        score=score,
    )


def _format_record(record: UserRecord, fmt: ReportFormat) -> str:
    match fmt:
        case ReportFormat.SUMMARY:
            return f"{record.name} ({record.status.value}) - Score: {record.score:.0f}"
        case ReportFormat.DETAIL:
            return (
                f"{record.name} <{record.email}>"
                f" | Status: {record.status.value}"
                f" | Days: {record.days_active:.0f}"
                f" | Score: {record.score:.0f}"
            )
        case _:
            return record.name


# ── Public API ─────────────────────────────────────────────────────────────────

def get_user_report(
    user_ids: Sequence[int],
    fmt: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """
    Fetch user data for each ID and return a formatted report string.

    Args:
        user_ids: Sequence of user IDs to include.
        fmt:      Output format — SUMMARY, DETAIL, or NAME_ONLY.

    Returns:
        A formatted multi-line report string, skipping any users that
        could not be fetched or whose data has an unexpected shape.
    """
    lines: list[str] = []

    for uid in user_ids:
        data   = _fetch_user(uid)
        if data is None:
            continue

        record = _parse_record(uid, data)
        if record is None:
            continue

        lines.append(_format_record(record, fmt))

    sep = "=" * 40
    return f"{sep}\nUSER REPORT\n{sep}\n" + "\n".join(lines)