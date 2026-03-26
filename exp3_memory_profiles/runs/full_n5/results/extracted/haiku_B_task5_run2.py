import logging
import requests
from typing import Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)

# Constants
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
SCORE_POINTS_MULTIPLIER = 1.5
SCORE_CONTRIBUTIONS_MULTIPLIER = 3
REPORT_WIDTH = 40

class UserStatus(Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"

@dataclass
class User:
    name: str
    email: str
    status: UserStatus
    days_active: float
    score: float

    def format_summary(self) -> str:
        return f"{self.name} ({self.status.value}) - Score: {self.score:.0f}"

    def format_detail(self) -> str:
        return (f"{self.name} <{self.email}> | Status: {self.status.value} | "
                f"Days: {self.days_active:.0f} | Score: {self.score:.0f}")

    def format_name_only(self) -> str:
        return self.name

class UserCache:
    """Simple in-memory cache for user data."""
    def __init__(self):
        self._cache = {}
    
    def get(self, user_id: int) -> Optional[dict]:
        return self._cache.get(user_id)
    
    def set(self, user_id: int, data: dict) -> None:
        self._cache[user_id] = data
    
    def clear(self) -> None:
        self._cache.clear()

def fetch_user_data(user_id: int, cache: UserCache) -> Optional[dict]:
    """Fetch user data from API, using cache first."""
    cached = cache.get(user_id)
    if cached:
        return cached
    
    try:
        resp = requests.get(
            f"{API_BASE_URL}/users/{user_id}",
            timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        cache.set(user_id, data)
        return data
    except requests.RequestException as e:
        logger.error(f"Failed to fetch user {user_id}: {e}")
        return None

def calculate_user_status(days_active: float) -> UserStatus:
    """Determine user status based on days active."""
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    elif days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW

def calculate_score(points: float, contributions: int) -> float:
    """Calculate user score from points and contributions."""
    return points * SCORE_POINTS_MULTIPLIER + contributions * SCORE_CONTRIBUTIONS_MULTIPLIER

def process_user(user_id: int, cache: UserCache) -> Optional[User]:
    """Process a single user's data into a User object."""
    data = fetch_user_data(user_id, cache)
    if not data:
        return None
    
    try:
        name = f"{data['first']} {data['last']}"
        email = data['contact']['email']
        created_ts = data['created_ts']
        
        days_active = (datetime.now(timezone.utc).timestamp() - created_ts) / SECONDS_PER_DAY
        status = calculate_user_status(days_active)
        score = calculate_score(data['points'], data['contributions'])
        
        return User(name=name, email=email, status=status, days_active=days_active, score=score)
    except KeyError as e:
        logger.error(f"Missing required field for user {user_id}: {e}")
        return None

def get_user_report(user_ids: list[int], format: str = "summary") -> str:
    """
    Generate a formatted user report.
    
    Args:
        user_ids: List of user IDs to report on
        format: Output format - "summary", "detail", or "name"
    
    Returns:
        Formatted report string
    """
    cache = UserCache()
    results = []
    
    for user_id in user_ids:
        user = process_user(user_id, cache)
        if user:
            if format == "summary":
                results.append(user.format_summary())
            elif format == "detail":
                results.append(user.format_detail())
            else:  # "name" or default
                results.append(user.format_name_only())
    
    header = "=" * REPORT_WIDTH + "\nUSER REPORT\n" + "=" * REPORT_WIDTH
    return header + "\n" + "\n".join(results)

report = get_user_report([123, 456, 789], format="detail")
print(report)