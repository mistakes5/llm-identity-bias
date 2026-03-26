import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any, List
import time
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Constants
SECONDS_PER_DAY = 86400
VETERAN_DAYS = 365
REGULAR_DAYS = 30
REQUEST_TIMEOUT = 3
API_BASE_URL = "https://api.example.com"
MAX_CACHE_SIZE = 1000
SCORE_MULTIPLIERS = {
    "points": 1.5,
    "contributions": 3.0,
}


class UserStatus(Enum):
    """User account status based on activity duration."""
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"


class ReportFormat(Enum):
    """Available report format options."""
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name_only"


@dataclass
class UserData:
    """Structured user information."""
    name: str
    email: str
    status: UserStatus
    days_active: float
    score: float

    def format(self, format_type: ReportFormat) -> str:
        """Format user data according to specified format."""
        if format_type == ReportFormat.SUMMARY:
            return f"{self.name} ({self.status.value}) - Score: {self.score:.0f}"
        elif format_type == ReportFormat.DETAIL:
            return (
                f"{self.name} <{self.email}> | Status: {self.status.value} | "
                f"Days: {self.days_active:.0f} | Score: {self.score:.0f}"
            )
        else:  # NAME_ONLY
            return self.name


class UserReportGenerator:
    """Manages user data fetching, caching, and report generation."""

    def __init__(self, base_url: str = API_BASE_URL, timeout: int = REQUEST_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
        self.cache: Dict[int, Dict[str, Any]] = {}
        self.session = self._create_session()

    @staticmethod
    def _create_session() -> requests.Session:
        """Create a requests session with retry strategy."""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _fetch_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch user data from API with error handling."""
        try:
            url = f"{self.base_url}/users/{user_id}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch user {user_id}: {e}")
            return None
        except ValueError as e:
            logger.error(f"Invalid JSON response for user {user_id}: {e}")
            return None

    def _get_cached_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user data from cache or fetch if not cached."""
        if user_id in self.cache:
            return self.cache[user_id]

        data = self._fetch_user(user_id)
        if data:
            # Simple cache eviction: clear if over max size
            if len(self.cache) >= MAX_CACHE_SIZE:
                self.cache.clear()
            self.cache[user_id] = data

        return data

    def _calculate_status(self, days_active: float) -> UserStatus:
        """Determine user status based on activity duration."""
        if days_active > VETERAN_DAYS:
            return UserStatus.VETERAN
        elif days_active > REGULAR_DAYS:
            return UserStatus.REGULAR
        else:
            return UserStatus.NEW

    def _calculate_score(self, data: Dict[str, Any]) -> float:
        """Calculate user score with safe key access."""
        try:
            points = data.get("points", 0)
            contributions = data.get("contributions", 0)
            return points * SCORE_MULTIPLIERS["points"] + contributions * SCORE_MULTIPLIERS["contributions"]
        except (TypeError, ValueError) as e:
            logger.warning(f"Invalid score calculation: {e}")
            return 0.0

    def _parse_user_data(self, raw_data: Dict[str, Any]) -> Optional[UserData]:
        """Parse and validate raw user data."""
        try:
            name = f"{raw_data['first']} {raw_data['last']}"
            email = raw_data["contact"]["email"]
            days_active = (time.time() - raw_data["created_ts"]) / SECONDS_PER_DAY
            status = self._calculate_status(days_active)
            score = self._calculate_score(raw_data)

            return UserData(
                name=name,
                email=email,
                status=status,
                days_active=days_active,
                score=score,
            )
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to parse user data: {e}")
            return None

    def generate_report(
        self,
        user_ids: List[int],
        format_type: str = "summary",
    ) -> str:
        """
        Generate a user report for the specified user IDs.

        Args:
            user_ids: List of user IDs to include in the report
            format_type: Report format ("summary", "detail", or "name_only")

        Returns:
            Formatted report string
        """
        # Validate format
        try:
            report_format = ReportFormat(format_type)
        except ValueError:
            raise ValueError(
                f"Invalid format: {format_type}. "
                f"Must be one of {[f.value for f in ReportFormat]}"
            )

        results = []
        for user_id in user_ids:
            raw_data = self._get_cached_user(user_id)
            if raw_data is None:
                logger.debug(f"Skipping user {user_id}: no data available")
                continue

            user_data = self._parse_user_data(raw_data)
            if user_data is None:
                logger.debug(f"Skipping user {user_id}: invalid data")
                continue

            results.append(user_data.format(report_format))

        # Format output
        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        body = "\n".join(results) if results else "No users found"
        return f"{header}\n{body}"

    def clear_cache(self) -> None:
        """Clear the user data cache."""
        self.cache.clear()


# Usage example
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    generator = UserReportGenerator()
    report = generator.generate_report([1, 2, 3], format_type="summary")
    print(report)