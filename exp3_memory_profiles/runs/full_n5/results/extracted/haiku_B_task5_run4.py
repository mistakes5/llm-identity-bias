import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)

# Configuration constants
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
API_TIMEOUT_SECONDS = 5
MAX_RETRIES = 2
POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3


class UserStatus(Enum):
    """User account status based on activity duration."""
    NEW = "new"
    REGULAR = "regular"
    VETERAN = "veteran"


class ReportFormat(Enum):
    """Output format for user reports."""
    BRIEF = "brief"
    SUMMARY = "summary"
    DETAIL = "detail"


@dataclass
class UserData:
    """Validated user information."""
    user_id: int
    first_name: str
    last_name: str
    email: str
    created_ts: float
    points: float
    contributions: int

    @property
    def days_active(self) -> float:
        return (time.time() - self.created_ts) / SECONDS_PER_DAY

    @property
    def status(self) -> UserStatus:
        if self.days_active > VETERAN_THRESHOLD_DAYS:
            return UserStatus.VETERAN
        elif self.days_active > REGULAR_THRESHOLD_DAYS:
            return UserStatus.REGULAR
        return UserStatus.NEW

    @property
    def score(self) -> float:
        return self.points * POINTS_MULTIPLIER + self.contributions * CONTRIBUTIONS_MULTIPLIER


class UserReportGenerator:
    """Generates user reports with caching and error handling."""

    def __init__(self, base_url: str = "https://api.example.com"):
        self.base_url = base_url
        self.cache: dict[int, UserData] = {}
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy."""
        session = requests.Session()
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _fetch_user(self, user_id: int) -> Optional[UserData]:
        """Fetch user data from API with error handling."""
        try:
            url = f"{self.base_url}/users/{user_id}"
            resp = self.session.get(url, timeout=API_TIMEOUT_SECONDS)
            resp.raise_for_status()
            raw_data = resp.json()
            return self._parse_user_data(user_id, raw_data)
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch user {user_id}: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid data structure for user {user_id}: {e}")
            return None

    @staticmethod
    def _parse_user_data(user_id: int, raw_data: dict) -> UserData:
        """Parse and validate raw API response."""
        try:
            return UserData(
                user_id=user_id,
                first_name=raw_data["first"],
                last_name=raw_data["last"],
                email=raw_data["contact"]["email"],
                created_ts=raw_data["created_ts"],
                points=float(raw_data.get("points", 0)),
                contributions=int(raw_data.get("contributions", 0)),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Missing or invalid required fields: {e}") from e

    def get_user_data(self, user_id: int) -> Optional[UserData]:
        """Get user data from cache or API."""
        if user_id in self.cache:
            return self.cache[user_id]
        user_data = self._fetch_user(user_id)
        if user_data:
            self.cache[user_id] = user_data
        return user_data

    def _format_line(self, user: UserData, fmt: ReportFormat) -> str:
        """Format a user entry according to the specified format."""
        name = f"{user.first_name} {user.last_name}"
        match fmt:
            case ReportFormat.BRIEF:
                return name
            case ReportFormat.SUMMARY:
                return f"{name} ({user.status.value}) - Score: {user.score:.0f}"
            case ReportFormat.DETAIL:
                return (
                    f"{name} <{user.email}> | Status: {user.status.value} | "
                    f"Days: {user.days_active:.0f} | Score: {user.score:.0f}"
                )

    def generate_report(self, user_ids: list[int], format: str = "summary") -> str:
        """Generate a formatted user report."""
        if not user_ids:
            logger.warning("No user IDs provided for report")
            return ""

        try:
            report_format = ReportFormat(format)
        except ValueError:
            logger.error(f"Invalid format '{format}'. Use: {', '.join(f.value for f in ReportFormat)}")
            raise

        lines = []
        for user_id in user_ids:
            user = self.get_user_data(user_id)
            if user:
                lines.append(self._format_line(user, report_format))

        if not lines:
            return "No user data available"

        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        return header + "\n" + "\n".join(lines)

    def clear_cache(self) -> None:
        """Clear the user data cache."""
        self.cache.clear()

    def __del__(self) -> None:
        """Clean up session on object destruction."""
        self.session.close()

# Old: Function-based, global cache, mutable default
report = get_user_report([1, 2, 3], format="summary")

# New: Class-based, per-instance cache, clean API
generator = UserReportGenerator()
report = generator.generate_report([1, 2, 3], format="summary")