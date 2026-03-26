import logging
import requests
from dataclasses import dataclass
from typing import Optional
from enum import Enum
import time

logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "https://api.example.com/users"
REQUEST_TIMEOUT = 3
CACHE_TTL = 3600  # seconds
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3


class UserStatus(Enum):
    """User account status based on activity duration."""
    NEW = "new"
    REGULAR = "regular"
    VETERAN = "veteran"


@dataclass
class UserData:
    """Validated user data from API."""
    first: str
    last: str
    email: str
    created_ts: float
    points: float
    contributions: int

    @staticmethod
    def from_api_response(data: dict) -> "UserData":
        """Parse and validate API response."""
        try:
            return UserData(
                first=str(data["first"]),
                last=str(data["last"]),
                email=str(data["contact"]["email"]),
                created_ts=float(data["created_ts"]),
                points=float(data.get("points", 0)),
                contributions=int(data.get("contributions", 0)),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Invalid API response: {e}")

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"

    @property
    def days_active(self) -> float:
        return (time.time() - self.created_ts) / 86400

    @property
    def status(self) -> UserStatus:
        if self.days_active > VETERAN_THRESHOLD_DAYS:
            return UserStatus.VETERAN
        elif self.days_active > REGULAR_THRESHOLD_DAYS:
            return UserStatus.REGULAR
        return UserStatus.NEW

    @property
    def score(self) -> float:
        return self.points * POINTS_MULTIPLIER + \
               self.contributions * CONTRIBUTIONS_MULTIPLIER


class UserReportGenerator:
    """Generate formatted user reports with caching."""

    def __init__(self):
        self._cache: dict[str, tuple[UserData, float]] = {}

    def _fetch_user_data(self, user_id: int) -> Optional[UserData]:
        """Fetch user data from cache or API."""
        cache_key = str(user_id)
        
        # Check cache
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < CACHE_TTL:
                return data
            del self._cache[cache_key]

        # Fetch from API
        try:
            response = requests.get(
                f"{API_BASE_URL}/{user_id}",
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            user_data = UserData.from_api_response(response.json())
            self._cache[cache_key] = (user_data, time.time())
            return user_data

        except requests.RequestException as e:
            logger.error(f"Failed to fetch user {user_id}: {e}")
            return None
        except ValueError as e:
            logger.error(f"Invalid user data for {user_id}: {e}")
            return None

    def _format_user(self, user: UserData, format_type: str) -> str:
        """Format user data according to type."""
        if format_type == "summary":
            return f"{user.full_name} ({user.status.value}) - Score: {user.score:.0f}"
        elif format_type == "detail":
            return (
                f"{user.full_name} <{user.email}> | "
                f"Status: {user.status.value} | "
                f"Days: {user.days_active:.0f} | "
                f"Score: {user.score:.0f}"
            )
        return user.full_name  # minimal

    def generate_report(
        self,
        user_ids: list[int],
        format_type: str = "summary",
    ) -> str:
        """Generate a formatted user report.
        
        Args:
            user_ids: User IDs to include.
            format_type: 'summary', 'detail', or 'minimal'.
            
        Returns:
            Formatted report string.
        """
        lines = []
        for user_id in user_ids:
            user_data = self._fetch_user_data(user_id)
            if user_data is not None:
                lines.append(self._format_user(user_data, format_type))

        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        body = "\n".join(lines) if lines else "(No valid users found)"
        return f"{header}\n{body}"