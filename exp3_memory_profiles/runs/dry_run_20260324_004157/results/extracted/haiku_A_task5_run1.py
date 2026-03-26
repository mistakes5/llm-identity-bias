"""User reporting module with caching and multiple output formats."""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_API_BASE = "https://api.example.com"
API_TIMEOUT = 3
SECONDS_PER_DAY = 86400

# Thresholds for user status
VETERAN_THRESHOLD = 365
REGULAR_THRESHOLD = 30

# Score calculation weights
POINTS_WEIGHT = 1.5
CONTRIBUTIONS_WEIGHT = 3


class ReportFormat(Enum):
    """Output format options for user reports."""
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name"


@dataclass
class UserData:
    """Represents a user with calculated fields."""
    first_name: str
    last_name: str
    email: str
    days_active: float
    score: float

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def status(self) -> str:
        """Determine user status based on tenure."""
        if self.days_active > VETERAN_THRESHOLD:
            return "veteran"
        elif self.days_active > REGULAR_THRESHOLD:
            return "regular"
        return "new"


class UserReportGenerator:
    """Generates user reports with caching."""

    def __init__(self, api_base: str = DEFAULT_API_BASE, cache_size: int = 1000):
        self.api_base = api_base
        self.cache = {}
        self.cache_size = cache_size
        self.api_timeout = API_TIMEOUT

    def get_user_report(
        self,
        user_ids: list[int],
        format: ReportFormat = ReportFormat.SUMMARY,
    ) -> str:
        """
        Generate a formatted report for the given user IDs.

        Args:
            user_ids: List of user IDs to include in the report
            format: Output format (SUMMARY, DETAIL, or NAME_ONLY)

        Returns:
            Formatted report string
        """
        users = []
        for uid in user_ids:
            user = self._fetch_user(uid)
            if user:
                users.append(user)
            else:
                logger.warning(f"Failed to fetch user {uid}")

        lines = [self._format_user(user, format) for user in users]
        return self._build_report(lines)

    def _fetch_user(self, user_id: int) -> Optional[UserData]:
        """
        Fetch user data from API or cache.

        Returns None if user cannot be fetched or parsed.
        """
        # Check cache
        if user_id in self.cache:
            return self.cache[user_id]

        # Fetch from API
        try:
            url = urljoin(self.api_base, f"/users/{user_id}")
            resp = requests.get(url, timeout=self.api_timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f"API request failed for user {user_id}: {e}")
            return None
        except ValueError as e:
            logger.error(f"Invalid JSON response for user {user_id}: {e}")
            return None

        # Parse and validate data
        try:
            user = self._parse_user_data(data)
            self._update_cache(user_id, user)
            return user
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to parse user data for {user_id}: {e}")
            return None

    def _parse_user_data(self, data: dict) -> UserData:
        """
        Parse raw API response into UserData.

        Raises KeyError or TypeError if data is malformed.
        """
        try:
            days_active = (time.time() - data["created_ts"]) / SECONDS_PER_DAY
            score = (
                data["points"] * POINTS_WEIGHT +
                data["contributions"] * CONTRIBUTIONS_WEIGHT
            )

            return UserData(
                first_name=data["first"],
                last_name=data["last"],
                email=data["contact"]["email"],
                days_active=days_active,
                score=score,
            )
        except (KeyError, TypeError) as e:
            raise KeyError(f"Missing required field: {e}")

    def _update_cache(self, user_id: int, user: UserData) -> None:
        """Update cache with size management."""
        if len(self.cache) >= self.cache_size:
            # Remove oldest entry (simple FIFO for now)
            oldest_id = next(iter(self.cache))
            del self.cache[oldest_id]
        self.cache[user_id] = user

    def _format_user(self, user: UserData, format: ReportFormat) -> str:
        """Format a single user based on output format."""
        match format:
            case ReportFormat.SUMMARY:
                return f"{user.full_name} ({user.status}) - Score: {user.score:.0f}"
            case ReportFormat.DETAIL:
                return (
                    f"{user.full_name} <{user.email}> | Status: {user.status} | "
                    f"Days: {user.days_active:.0f} | Score: {user.score:.0f}"
                )
            case ReportFormat.NAME_ONLY:
                return user.full_name

    def _build_report(self, lines: list[str]) -> str:
        """Build formatted report with header."""
        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        return header + "\n" + "\n".join(lines)

    def clear_cache(self) -> None:
        """Clear the cache."""
        self.cache.clear()


# Backward-compatible function interface
_default_generator = UserReportGenerator()


def get_user_report(
    user_ids: list[int],
    format: str = "summary",
) -> str:
    """
    Generate a user report (backward-compatible interface).

    Args:
        user_ids: List of user IDs
        format: Output format ('summary', 'detail', or 'name')

    Returns:
        Formatted report string
    """
    report_format = ReportFormat(format)
    return _default_generator.get_user_report(user_ids, report_format)

gen = UserReportGenerator()
user = gen._parse_user_data({"first": "Alice", "last": "Smith", "contact": {"email": "a@example.com"}, "points": 100, "contributions": 5, "created_ts": time.time() - 365*86400})
assert user.status == "veteran"