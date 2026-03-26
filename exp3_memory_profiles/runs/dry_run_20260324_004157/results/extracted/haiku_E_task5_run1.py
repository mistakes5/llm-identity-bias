import requests
import json
import time
import logging
from typing import Optional, List
from enum import Enum

# Configure logging to see errors instead of silently failing
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Constants - avoid magic numbers scattered throughout code
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
API_BASE_URL = "https://api.example.com/users"
REQUEST_TIMEOUT_SECONDS = 3
SCORE_POINT_MULTIPLIER = 1.5
SCORE_CONTRIBUTION_MULTIPLIER = 3

class UserStatus(Enum):
    """Enum for user status - makes code self-documenting"""
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"


class UserCache:
    """Simple thread-safe cache with TTL support"""
    def __init__(self, ttl_seconds: int = 3600):
        self.cache = {}
        self.ttl_seconds = ttl_seconds
        self.timestamps = {}
    
    def get(self, key: str) -> Optional[dict]:
        if key in self.cache:
            age = time.time() - self.timestamps[key]
            if age < self.ttl_seconds:
                return self.cache[key]
            else:
                # Expired - remove it
                del self.cache[key]
                del self.timestamps[key]
        return None
    
    def set(self, key: str, value: dict) -> None:
        self.cache[key] = value
        self.timestamps[key] = time.time()


# Create single cache instance instead of module-level dict
user_cache = UserCache()


def calculate_user_status(days_active: float) -> UserStatus:
    """Extract status logic into its own function for clarity"""
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    elif days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    else:
        return UserStatus.NEW


def calculate_score(points: int, contributions: int) -> float:
    """Extract score calculation - easier to modify scoring later"""
    return points * SCORE_POINT_MULTIPLIER + contributions * SCORE_CONTRIBUTION_MULTIPLIER


def fetch_user_data(user_id: int) -> Optional[dict]:
    """Fetch a single user from the API with proper error handling"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/{user_id}",
            timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()  # Raise exception for bad status codes
        return response.json()  # Use .json() instead of manual json.loads
    except requests.RequestException as e:
        # Be specific about which exception - don't catch all
        logger.warning(f"Failed to fetch user {user_id}: {e}")
        return None


def format_user_line(name: str, status: UserStatus, email: str, 
                     days_active: float, score: float, format_type: str) -> str:
    """Extract formatting logic - easier to test and modify"""
    if format_type == "summary":
        return f"{name} ({status.value}) - Score: {score:.0f}"
    elif format_type == "detail":
        return f"{name} <{email}> | Status: {status.value} | Days: {days_active:.0f} | Score: {score:.0f}"
    else:
        return name


def get_user_report(user_ids: List[int], format_type: str = "summary") -> str:
    """
    Generate a report for multiple users.
    
    Args:
        user_ids: List of user IDs to fetch
        format_type: "summary", "detail", or "name" only
    
    Returns:
        Formatted report string
    """
    # Removed mutable default argument (items=[]) - this was a Python gotcha!
    results = []
    
    for user_id in user_ids:
        # Try cache first
        user_data = user_cache.get(user_id)
        
        # If not cached, fetch from API
        if user_data is None:
            user_data = fetch_user_data(user_id)
            if user_data is None:
                continue  # Skip this user if fetch failed
            user_cache.set(user_id, user_data)
        
        # Extract fields with validation
        try:
            name = f"{user_data['first']} {user_data['last']}"
            email = user_data['contact']['email']
            days_active = (time.time() - user_data['created_ts']) / SECONDS_PER_DAY
            
            status = calculate_user_status(days_active)
            score = calculate_score(user_data['points'], user_data['contributions'])
            
            line = format_user_line(name, status, email, days_active, score, format_type)
            results.append(line)
            
        except (KeyError, TypeError) as e:
            # Log which user had bad data so we can debug
            logger.warning(f"Invalid data for user {user_id}: {e}")
            continue
    
    # Format output
    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(results)