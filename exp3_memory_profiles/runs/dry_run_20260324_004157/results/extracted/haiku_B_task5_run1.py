import requests
import json
import time
import logging
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Constants
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
SCORE_POINT_MULTIPLIER = 1.5
SCORE_CONTRIBUTION_MULTIPLIER = 3
API_TIMEOUT = 10
API_BASE_URL = "https://api.example.com"

class UserStatus(Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"

@dataclass
class UserInfo:
    name: str
    email: str
    status: UserStatus
    days_active: float
    score: float

class UserReportGenerator:
    """Generates user reports with optional caching."""
    
    def __init__(self, base_url: str = API_BASE_URL, timeout: int = API_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
        self._cache: Dict[int, Dict[str, Any]] = {}
    
    def _fetch_user_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch user data from API with error handling."""
        if user_id in self._cache:
            return self._cache[user_id]
        
        try:
            url = f"{self.base_url}/users/{user_id}"
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            self._cache[user_id] = data
            return data
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch user {user_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON for user {user_id}: {e}")
            return None
    
    def _calculate_status(self, days_active: float) -> UserStatus:
        """Determine user status based on account age."""
        if days_active > VETERAN_THRESHOLD_DAYS:
            return UserStatus.VETERAN
        elif days_active > REGULAR_THRESHOLD_DAYS:
            return UserStatus.REGULAR
        return UserStatus.NEW
    
    def _calculate_score(self, points: float, contributions: float) -> float:
        """Calculate user score from metrics."""
        return points * SCORE_POINT_MULTIPLIER + contributions * SCORE_CONTRIBUTION_MULTIPLIER
    
    def _parse_user_info(self, user_id: int, data: Dict[str, Any]) -> Optional[UserInfo]:
        """Extract and validate user information from raw data."""
        try:
            name = f"{data['first']} {data['last']}"
            email = data.get('contact', {}).get('email', 'unknown@example.com')
            created_ts = data.get('created_ts', time.time())
            days_active = (time.time() - created_ts) / SECONDS_PER_DAY
            
            status = self._calculate_status(days_active)
            score = self._calculate_score(
                data.get('points', 0),
                data.get('contributions', 0)
            )
            
            return UserInfo(
                name=name,
                email=email,
                status=status,
                days_active=days_active,
                score=score
            )
        except (KeyError, TypeError) as e:
            logger.warning(f"Invalid data structure for user {user_id}: {e}")
            return None
    
    def _format_user(self, user: UserInfo, format: str = "summary") -> str:
        """Format user info according to specified format."""
        if format == "summary":
            return f"{user.name} ({user.status.value}) - Score: {user.score:.0f}"
        elif format == "detail":
            return (
                f"{user.name} <{user.email}> | Status: {user.status.value} | "
                f"Days: {user.days_active:.0f} | Score: {user.score:.0f}"
            )
        else:
            return user.name
    
    def generate_report(
        self,
        user_ids: List[int],
        format: str = "summary"
    ) -> str:
        """Generate a formatted user report.
        
        Args:
            user_ids: List of user IDs to include
            format: Output format ('summary', 'detail', or 'name')
        
        Returns:
            Formatted report string
        """
        results = []
        
        for user_id in user_ids:
            data = self._fetch_user_data(user_id)
            if not data:
                continue
            
            user_info = self._parse_user_info(user_id, data)
            if not user_info:
                continue
            
            line = self._format_user(user_info, format)
            results.append(line)
        
        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        return header + "\n" + "\n".join(results)
    
    def clear_cache(self) -> None:
        """Clear the user data cache."""
        self._cache.clear()


# Usage
if __name__ == "__main__":
    generator = UserReportGenerator()
    report = generator.generate_report([1, 2, 3], format="summary")
    print(report)