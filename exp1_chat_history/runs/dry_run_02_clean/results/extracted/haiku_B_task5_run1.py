import requests
import json
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Constants
API_BASE_URL = "https://api.example.com"
API_TIMEOUT = 3
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
SCORE_POINTS_MULTIPLIER = 1.5
SCORE_CONTRIBUTIONS_MULTIPLIER = 3


@dataclass
class UserStatus:
    name: str
    email: str
    status: str
    days_active: float
    score: float

    def format_summary(self) -> str:
        return f"{self.name} ({self.status}) - Score: {self.score:.0f}"

    def format_detail(self) -> str:
        return f"{self.name} <{self.email}> | Status: {self.status} | Days: {self.days_active:.0f} | Score: {self.score:.0f}"

    def format_simple(self) -> str:
        return self.name


class UserReportGenerator:
    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl
        self.cache = {}
        self.cache_timestamps = {}

    def _is_cache_valid(self, user_id: int) -> bool:
        """Check if cached data is still fresh."""
        if user_id not in self.cache_timestamps:
            return False
        age = datetime.now() - self.cache_timestamps[user_id]
        return age < timedelta(seconds=self.cache_ttl)

    def _fetch_user_data(self, user_id: int) -> Optional[dict]:
        """Fetch user data from API with error handling."""
        if self._is_cache_valid(user_id):
            return self.cache[user_id]

        try:
            url = f"{API_BASE_URL}/users/{user_id}"
            response = requests.get(url, timeout=API_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            # Cache the result
            self.cache[user_id] = data
            self.cache_timestamps[user_id] = datetime.now()
            return data
            
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch user {user_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response for user {user_id}: {e}")
            return None

    def _get_user_status(self, days_active: float) -> str:
        """Determine user status based on days active."""
        if days_active > VETERAN_THRESHOLD_DAYS:
            return "veteran"
        elif days_active > REGULAR_THRESHOLD_DAYS:
            return "regular"
        return "new"

    def _calculate_score(self, points: float, contributions: int) -> float:
        """Calculate user score."""
        return points * SCORE_POINTS_MULTIPLIER + contributions * SCORE_CONTRIBUTIONS_MULTIPLIER

    def _build_user_status(self, data: dict) -> Optional[UserStatus]:
        """Extract and validate user information."""
        try:
            name = f"{data['first']} {data['last']}"
            email = data.get('contact', {}).get('email', 'N/A')
            created_ts = data.get('created_ts', 0)
            days_active = (datetime.now().timestamp() - created_ts) / SECONDS_PER_DAY
            
            status = self._get_user_status(days_active)
            score = self._calculate_score(data.get('points', 0), data.get('contributions', 0))
            
            return UserStatus(
                name=name,
                email=email,
                status=status,
                days_active=days_active,
                score=score
            )
        except KeyError as e:
            logger.error(f"Missing required field in user data: {e}")
            return None

    def generate_report(self, user_ids: list[int], format: str = "summary") -> str:
        """Generate user report in specified format.
        
        Args:
            user_ids: List of user IDs to include
            format: Output format - "summary", "detail", or "simple"
            
        Returns:
            Formatted report string
        """
        valid_formats = {"summary", "detail", "simple"}
        if format not in valid_formats:
            raise ValueError(f"Format must be one of {valid_formats}")

        results = []
        
        for user_id in user_ids:
            data = self._fetch_user_data(user_id)
            if data is None:
                continue
            
            user_status = self._build_user_status(data)
            if user_status is None:
                continue
            
            # Format based on requested format
            if format == "summary":
                line = user_status.format_summary()
            elif format == "detail":
                line = user_status.format_detail()
            else:  # simple
                line = user_status.format_simple()
            
            results.append(line)
        
        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        return header + "\n" + "\n".join(results)


# Usage
if __name__ == "__main__":
    generator = UserReportGenerator()
    report = generator.generate_report([1, 2, 3], format="summary")
    print(report)