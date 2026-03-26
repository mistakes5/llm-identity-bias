import json
import logging
import time
from typing import Optional
from dataclasses import dataclass
import requests

# Configuration constants
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
API_TIMEOUT_SECONDS = 3
API_BASE_URL = "https://api.example.com"

POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3

logger = logging.getLogger(__name__)


@dataclass
class UserData:
    """Represents user information from the API."""
    first_name: str
    last_name: str
    email: str
    days_active: float
    score: float

    @property
    def status(self) -> str:
        """Determine user status based on account age."""
        if self.days_active > VETERAN_THRESHOLD_DAYS:
            return "veteran"
        elif self.days_active > REGULAR_THRESHOLD_DAYS:
            return "regular"
        return "new"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class UserReportGenerator:
    """Generates user reports with proper caching and error handling."""

    def __init__(self, base_url: str = API_BASE_URL, timeout: int = API_TIMEOUT_SECONDS):
        self.base_url = base_url
        self.timeout = timeout
        self._cache: dict[int, Optional[UserData]] = {}

    def _fetch_user_data(self, user_id: int) -> Optional[dict]:
        """Fetch raw user data from API with proper error handling."""
        try:
            url = f"{self.base_url}/users/{user_id}"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch user {user_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response for user {user_id}: {e}")
            return None

    def _parse_user_data(self, raw_data: dict) -> Optional[UserData]:
        """Parse and validate raw API response into UserData."""
        try:
            first_name = raw_data.get("first", "Unknown")
            last_name = raw_data.get("last", "Unknown")
            email = raw_data.get("contact", {}).get("email", "unknown@example.com")
            created_ts = raw_data.get("created_ts", 0)

            if not isinstance(created_ts, (int, float)):
                logger.warning(f"Invalid created_ts format: {created_ts}")
                return None

            days_active = max(0, (time.time() - created_ts) / SECONDS_PER_DAY)
            points = raw_data.get("points", 0)
            contributions = raw_data.get("contributions", 0)
            score = points * POINTS_MULTIPLIER + contributions * CONTRIBUTIONS_MULTIPLIER

            return UserData(
                first_name=first_name,
                last_name=last_name,
                email=email,
                days_active=days_active,
                score=score,
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Error parsing user data: {e}")
            return None

    def get_user(self, user_id: int) -> Optional[UserData]:
        """Get user data, using cache if available."""
        if user_id in self._cache:
            return self._cache[user_id]

        raw_data = self._fetch_user_data(user_id)
        if not raw_data:
            self._cache[user_id] = None
            return None

        user_data = self._parse_user_data(raw_data)
        self._cache[user_id] = user_data
        return user_data

    def format_user(self, user: UserData, format_type: str = "summary") -> str:
        """Format user data based on format type."""
        if format_type == "summary":
            return f"{user.full_name} ({user.status}) - Score: {user.score:.0f}"
        elif format_type == "detail":
            return (
                f"{user.full_name} <{user.email}> | Status: {user.status} | "
                f"Days: {user.days_active:.0f} | Score: {user.score:.0f}"
            )
        else:  # simple
            return user.full_name

    def generate_report(self, user_ids: list[int], format_type: str = "summary") -> str:
        """Generate a formatted user report."""
        results = []
        for user_id in user_ids:
            user = self.get_user(user_id)
            if user:
                results.append(self.format_user(user, format_type))
            else:
                logger.debug(f"Skipping user {user_id} - unable to fetch or parse")

        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        body = "\n".join(results) if results else "(No users found)"
        return f"{header}\n{body}"


# Maintain simple interface
_generator = UserReportGenerator()

def get_user_report(user_ids: list[int], format: str = "summary") -> str:
    """Generate a user report."""
    return _generator.generate_report(user_ids, format_type=format)