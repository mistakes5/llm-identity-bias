"""User report generation with caching and structured formatting."""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

BASE_API_URL = "https://api.example.com/users"
REQUEST_TIMEOUT_SECONDS = 3
SECONDS_PER_DAY = 86_400

VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30

# ── Types ────────────────────────────────────────────────────────────────────

class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name"

class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"

@dataclass(frozen=True)
class UserRecord:
    name: str
    email: str
    days_active: float
    score: float
    status: UserStatus

# ── Cache ────────────────────────────────────────────────────────────────────

_cache: dict[int, dict] = {}

# ── Internal helpers ─────────────────────────────────────────────────────────

def _fetch_user(user_id: int) -> Optional[dict]:
    """Return raw user data from cache or API. Returns None on failure."""
    if user_id in _cache:
        return _cache[user_id]
    try:
        response = requests.get(f"{BASE_API_URL}/{user_id}", timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data: dict = response.json()
        _cache[user_id] = data
        return data
    except RequestException as exc:
        logger.warning("Failed to fetch user %d: %s", user_id, exc)
        return None

def _classify_status(days_active: float) -> UserStatus:
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    if days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW

def _compute_score(points: float, contributions: float) -> float:
    # TODO: your scoring formula here (5–10 lines)
    raise NotImplementedError

def _parse_user(data: dict) -> UserRecord:
    name = f"{data['first']} {data['last']}"
    email = data["contact"]["email"]
    days_active = (time.time() - data["created_ts"]) / SECONDS_PER_DAY
    score = _compute_score(data["points"], data["contributions"])
    return UserRecord(name=name, email=email, days_active=days_active,
                      score=score, status=_classify_status(days_active))

def _format_record(record: UserRecord, fmt: ReportFormat) -> str:
    if fmt == ReportFormat.SUMMARY:
        return f"{record.name} ({record.status.value}) - Score: {record.score:.0f}"
    if fmt == ReportFormat.DETAIL:
        return (f"{record.name} <{record.email}> | Status: {record.status.value}"
                f" | Days: {record.days_active:.0f} | Score: {record.score:.0f}")
    return record.name

# ── Public API ────────────────────────────────────────────────────────────────

def get_user_report(
    user_ids: list[int],
    report_format: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    lines: list[str] = []
    for uid in user_ids:
        raw = _fetch_user(uid)
        if raw is None:
            continue
        try:
            record = _parse_user(raw)
        except KeyError as exc:
            logger.warning("Skipping user %d — missing field: %s", uid, exc)
            continue
        lines.append(_format_record(record, report_format))

    divider = "=" * 40
    return "\n".join([f"{divider}\nUSER REPORT\n{divider}", *lines])