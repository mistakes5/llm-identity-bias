import requests
import json
import time
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

# Constants
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
SCORE_POINTS_MULTIPLIER = 1.5
SCORE_CONTRIBUTIONS_MULTIPLIER = 3

class UserStatus(Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"

@dataclass
class UserData:
    name: str
    email: str
    status: UserStatus
    days_active: float
    score: float

def _calculate_days_active(created_ts: float) -> float:
    """Convert creation timestamp to days since account creation."""
    return (time.time() - created_ts) / SECONDS_PER_DAY

def _determine_status(days_active: float) -> UserStatus:
    """Determine user status based on account age."""
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    elif days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    else:
        return UserStatus.NEW

def _calculate_score(points: int, contributions: int) -> float:
    """Calculate user engagement score."""
    return points * SCORE_POINTS_MULTIPLIER + contributions * SCORE_CONTRIBUTIONS_MULTIPLIER

def _fetch_user_data(user_id: int) -> Optional[dict]:
    """Fetch user data from API with error handling."""
    try:
        url = f"{API_BASE_URL}/users/{user_id}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()  # Raise exception for bad status codes
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching user {user_id}: {e}")
        return None

# Simple in-memory cache with TTL (optional: use cachetools.TTLCache for production)
class SimpleCache:
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: dict[int, tuple[dict, float]] = {}
        self.ttl_seconds = ttl_seconds
    
    def get(self, key: int) -> Optional[dict]:
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                return data
            else:
                del self._cache[key]  # Remove expired entry
        return None
    
    def set(self, key: int, value: dict) -> None:
        self._cache[key] = (value, time.time())

cache = SimpleCache(ttl_seconds=3600)

def _parse_user_data(raw_data: dict) -> UserData:
    """Parse raw API response into UserData object."""
    name = f"{raw_data['first']} {raw_data['last']}"
    email = raw_data["contact"]["email"]
    days_active = _calculate_days_active(raw_data["created_ts"])
    status = _determine_status(days_active)
    score = _calculate_score(raw_data["points"], raw_data["contributions"])
    
    return UserData(name=name, email=email, status=status, days_active=days_active, score=score)

def _format_user_line(user: UserData, format: str) -> str:
    """Format a single user record according to the requested format."""
    if format == "summary":
        return f"{user.name} ({user.status.value}) - Score: {user.score:.0f}"
    elif format == "detail":
        return f"{user.name} <{user.email}> | Status: {user.status.value} | Days: {user.days_active:.0f} | Score: {user.score:.0f}"
    elif format == "name":
        return user.name
    else:
        raise ValueError(f"Unknown format: {format}")

def get_user_report(user_ids: list[int], format: str = "summary") -> str:
    """Generate a report for the given user IDs.
    
    Args:
        user_ids: List of user IDs to include in the report
        format: Output format - "summary", "detail", or "name"
    
    Returns:
        Formatted user report as a string
    """
    results = []
    
    for user_id in user_ids:
        # Try cache first
        raw_data = cache.get(user_id)
        
        # Fetch if not in cache
        if raw_data is None:
            raw_data = _fetch_user_data(user_id)
        
        # Skip if fetch failed
        if raw_data is None:
            continue
        
        # Cache the result
        cache.set(user_id, raw_data)
        
        # Parse and format
        try:
            user_data = _parse_user_data(raw_data)
            line = _format_user_line(user_data, format)
            results.append(line)
        except (KeyError, ValueError) as e:
            print(f"Error parsing user {user_id} data: {e}")
            continue
    
    # Generate report
    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(results)