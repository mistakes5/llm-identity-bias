import logging
import requests
import json
import time
from typing import TypedDict, Optional
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)

# Constants
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
SCORE_POINT_MULTIPLIER = 1.5
SCORE_CONTRIBUTION_MULTIPLIER = 3
API_BASE_URL = "https://api.example.com"
API_TIMEOUT_SECONDS = 3

class UserData(TypedDict):
    first: str
    last: str
    contact: dict
    created_ts: float
    points: float
    contributions: float

@dataclass
class UserInfo:
    name: str
    email: str
    status: str
    days_active: float
    score: float

def calculate_status(days_active: float) -> str:
    """Determine user status based on account age."""
    if days_active > VETERAN_THRESHOLD_DAYS:
        return "veteran"
    elif days_active > REGULAR_THRESHOLD_DAYS:
        return "regular"
    return "new"

def calculate_score(points: float, contributions: float) -> float:
    """Calculate user engagement score."""
    return points * SCORE_POINT_MULTIPLIER + contributions * SCORE_CONTRIBUTION_MULTIPLIER

def fetch_user(user_id: int, cache: dict) -> Optional[UserData]:
    """Fetch user data from API with caching. Returns None if fetch fails."""
    if user_id in cache:
        return cache[user_id]
    
    try:
        resp = requests.get(
            f"{API_BASE_URL}/users/{user_id}",
            timeout=API_TIMEOUT_SECONDS
        )
        resp.raise_for_status()
        data = resp.json()
        cache[user_id] = data
        return data
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch user {user_id}: {e}")
        return None

def process_user(user_data: UserData) -> UserInfo:
    """Extract and calculate user information."""
    name = f"{user_data['first']} {user_data['last']}"
    email = user_data['contact']['email']
    days_active = (time.time() - user_data['created_ts']) / SECONDS_PER_DAY
    status = calculate_status(days_active)
    score = calculate_score(user_data['points'], user_data['contributions'])
    
    return UserInfo(
        name=name,
        email=email,
        status=status,
        days_active=days_active,
        score=score
    )

def format_user(user_info: UserInfo, format_type: str = "summary") -> str:
    """Format user information for display."""
    if format_type == "summary":
        return f"{user_info.name} ({user_info.status}) - Score: {user_info.score:.0f}"
    elif format_type == "detail":
        return (f"{user_info.name} <{user_info.email}> | "
                f"Status: {user_info.status} | "
                f"Days: {user_info.days_active:.0f} | "
                f"Score: {user_info.score:.0f}")
    return user_info.name

def get_user_report(user_ids: list[int], format_type: str = "summary") -> str:
    """Generate a report for multiple users."""
    cache = {}  # Dependency injection - caller can pass cache if needed
    results = []
    
    for user_id in user_ids:
        user_data = fetch_user(user_id, cache)
        if user_data is None:
            continue
        
        try:
            user_info = process_user(user_data)
            formatted = format_user(user_info, format_type)
            results.append(formatted)
        except KeyError as e:
            logger.error(f"Missing field in user {user_id}: {e}")
            continue
    
    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(results)