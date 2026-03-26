"""User report generation with caching and formatting."""

import logging
import requests
from datetime import datetime
from typing import Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Constants — extract magic numbers and strings
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3
DAYS_VETERAN_THRESHOLD = 365
DAYS_REGULAR_THRESHOLD = 30
SCORE_MULTIPLIER_POINTS = 1.5
SCORE_MULTIPLIER_CONTRIBUTIONS = 3

class UserStatus(str, Enum):
    """User tenure status."""
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"

class ReportFormat(str, Enum):
    """Report output format."""
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name"

@dataclass
class UserData:
    """Structured user data from API."""
    first_name: str
    last_name: str
    email: str
    created_ts: float
    points: float
    contributions: int

class UserReportCache:
    """Thread-safe cache for user data."""

    def __init__(self):
        self._cache: dict[int, UserData] = {}

    def get(self, user_id: int) -> Optional[UserData]:
        return self._cache.get(user_id)

    def set(self, user_id: int, data: UserData) -> None:
        self._cache[user_id] = data

def _fetch_user_data(user_id: int, cache: UserReportCache) -> Optional[UserData]:
    """Fetch user data from API with proper error handling."""
    cached = cache.get(user_id)
    if cached:
        return cached

    try:
        url = f"{API_BASE_URL}/users/{user_id}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        raw_data = response.json()
        user_data = UserData(
            first_name=raw_data.get("first", ""),
            last_name=raw_data.get("last", ""),
            email=raw_data.get("contact", {}).get("email", ""),
            created_ts=raw_data.get("created_ts", 0),
            points=raw_data.get("points", 0),
            contributions=raw_data.get("contributions", 0),
        )
        cache.set(user_id, user_data)
        return user_data

    except requests.RequestException as e:
        logger.warning(f"Failed to fetch user {user_id}: {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid data format for user {user_id}: {e}")
        return None

def _calculate_status(days_active: float) -> UserStatus:
    """Determine user status based on account age."""
    if days_active > DAYS_VETERAN_THRESHOLD:
        return UserStatus.VETERAN
    elif days_active > DAYS_REGULAR_THRESHOLD:
        return UserStatus.REGULAR
    else:
        return UserStatus.NEW

def _format_user_line(user_data: UserData, format_type: ReportFormat) -> str:
    """Format a single user record for output."""
    full_name = f"{user_data.first_name} {user_data.last_name}".strip()
    days_active = (datetime.now().timestamp() - user_data.created_ts) / 86400
    status = _calculate_status(days_active)
    score = user_data.points * SCORE_MULTIPLIER_POINTS + user_data.contributions * SCORE_MULTIPLIER_CONTRIBUTIONS

    if format_type == ReportFormat.SUMMARY:
        return f"{full_name} ({status.value}) - Score: {score:.0f}"
    elif format_type == ReportFormat.DETAIL:
        return f"{full_name} <{user_data.email}> | Status: {status.value} | Days: {days_active:.0f} | Score: {score:.0f}"
    else:
        return full_name

def get_user_report(
    user_ids: list[int],
    format_type: str = "summary",
    cache: Optional[UserReportCache] = None,
) -> str:
    """Generate a formatted report of user data.

    Args:
        user_ids: List of user IDs to include in report
        format_type: Output format ("summary", "detail", or "name")
        cache: Optional cache instance. Creates new one if not provided.

    Returns:
        Formatted report string
    """
    try:
        report_format = ReportFormat(format_type)
    except ValueError:
        raise ValueError(
            f"Invalid format '{format_type}'. "
            f"Must be one of: {', '.join(f.value for f in ReportFormat)}"
        )

    if cache is None:
        cache = UserReportCache()

    lines = []
    for user_id in user_ids:
        user_data = _fetch_user_data(user_id, cache)
        if user_data:
            line = _format_user_line(user_data, report_format)
            lines.append(line)

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    body = "\n".join(lines) if lines else "(No valid users found)"
    return f"{header}\n{body}"