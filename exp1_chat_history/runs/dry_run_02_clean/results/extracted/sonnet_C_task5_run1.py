import logging
import time
from dataclasses import dataclass
from enum import Enum

import requests

logger = logging.getLogger(__name__)

# Module-level cache — keyed by user ID
_cache: dict[int, dict] = {}

# Named constants instead of magic numbers
POINTS_WEIGHT = 1.5
CONTRIBUTIONS_WEIGHT = 3.0
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30


class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name"


@dataclass(frozen=True)
class UserRecord:
    name: str
    email: str
    days_active: float
    score: float
    status: str


def _fetch_user(uid: int) -> dict | None:
    """Fetch user data from the API, using the module cache to avoid repeat calls."""
    if uid in _cache:
        return _cache[uid]

    try:
        response = requests.get(
            f"https://api.example.com/users/{uid}",
            timeout=3,
        )
        response.raise_for_status()
        data = response.json()
        _cache[uid] = data
        return data
    except requests.RequestException as exc:
        logger.warning("Failed to fetch user %s: %s", uid, exc)
        return None


def _parse_user(data: dict) -> UserRecord:
    """Build a structured UserRecord from raw API response data."""
    name = f"{data['first']} {data['last']}"
    email = data["contact"]["email"]
    days_active = (time.time() - data["created_ts"]) / 86400

    if days_active > VETERAN_THRESHOLD_DAYS:
        status = "veteran"
    elif days_active > REGULAR_THRESHOLD_DAYS:
        status = "regular"
    else:
        status = "new"

    score = (
        data["points"] * POINTS_WEIGHT
        + data["contributions"] * CONTRIBUTIONS_WEIGHT
    )

    return UserRecord(
        name=name,
        email=email,
        days_active=days_active,
        score=score,
        status=status,
    )


def _format_record(record: UserRecord, report_format: ReportFormat) -> str:
    """Render a single UserRecord as a report line."""
    if report_format == ReportFormat.DETAIL:
        return (
            f"{record.name} <{record.email}> | "
            f"Status: {record.status} | "
            f"Days: {record.days_active:.0f} | "
            f"Score: {record.score:.0f}"
        )
    if report_format == ReportFormat.SUMMARY:
        return f"{record.name} ({record.status}) - Score: {record.score:.0f}"
    return record.name


def get_user_report(
    user_ids: list[int],
    report_format: ReportFormat | str = ReportFormat.SUMMARY,
) -> str:
    """
    Fetch a list of users and return a formatted report string.

    Args:
        user_ids: User IDs to include.
        report_format: One of 'summary', 'detail', or 'name'.

    Returns:
        Report string with a header and one line per successfully fetched user.
    """
    if isinstance(report_format, str):
        report_format = ReportFormat(report_format)

    lines: list[str] = []
    for uid in user_ids:
        data = _fetch_user(uid)
        if data is None:
            continue

        try:
            record = _parse_user(data)
        except KeyError as exc:
            logger.warning("Malformed user data for uid=%s, missing key %s", uid, exc)
            continue

        lines.append(_format_record(record, report_format))

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(lines)