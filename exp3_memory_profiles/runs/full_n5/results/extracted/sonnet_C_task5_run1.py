import time
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# Named constants instead of magic numbers
SECONDS_PER_DAY = 86_400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3.0
REQUEST_TIMEOUT_SECONDS = 3
API_BASE_URL = "https://api.example.com/users"


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
    name: str
    email: str
    days_active: float
    score: float
    status: UserStatus


# Module-level cache — explicit and typed
_user_cache: dict[int, dict] = {}


def _fetch_user(uid: int) -> Optional[dict]:
    """Fetch a single user from the API, using cache if available."""
    if uid in _user_cache:
        return _user_cache[uid]

    try:
        resp = requests.get(f"{API_BASE_URL}/{uid}", timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        _user_cache[uid] = data
        return data
    except requests.RequestException as exc:
        logger.warning("Failed to fetch user %d: %s", uid, exc)
        return None


def _parse_user(data: dict) -> UserRecord:
    """Transform raw API data into a structured UserRecord."""
    name = f"{data['first']} {data['last']}"
    email = data["contact"]["email"]
    days_active = (time.time() - data["created_ts"]) / SECONDS_PER_DAY
    score = data["points"] * POINTS_MULTIPLIER + data["contributions"] * CONTRIBUTIONS_MULTIPLIER

    if days_active > VETERAN_THRESHOLD_DAYS:
        status = UserStatus.VETERAN
    elif days_active > REGULAR_THRESHOLD_DAYS:
        status = UserStatus.REGULAR
    else:
        status = UserStatus.NEW

    return UserRecord(name=name, email=email, days_active=days_active, score=score, status=status)


def _format_user(user: UserRecord, report_format: ReportFormat) -> str:
    """Render a single UserRecord as a string for the given format."""
    match report_format:
        case ReportFormat.SUMMARY:
            return f"{user.name} ({user.status}) - Score: {user.score:.0f}"
        case ReportFormat.DETAIL:
            return (
                f"{user.name} <{user.email}> | "
                f"Status: {user.status} | "
                f"Days: {user.days_active:.0f} | "
                f"Score: {user.score:.0f}"
            )
        case ReportFormat.NAME_ONLY:
            return user.name


def get_user_report(
    user_ids: list[int],
    report_format: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """
    Fetch and format a report for the given user IDs.

    Args:
        user_ids: List of user IDs to include in the report.
        report_format: Controls the verbosity of each line.

    Returns:
        A formatted multi-line report string. Users that fail
        to fetch are skipped with a warning logged.
    """
    lines: list[str] = []

    for uid in user_ids:
        data = _fetch_user(uid)
        if data is None:
            continue

        try:
            user = _parse_user(data)
        except KeyError as exc:
            logger.warning("Skipping user %d — missing field %s", uid, exc)
            continue

        lines.append(_format_user(user, report_format))

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(lines)