import logging
import requests
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Constants
API_BASE_URL = "https://api.example.com/users"
REQUEST_TIMEOUT = 3
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
SCORE_POINTS_MULTIPLIER = 1.5
SCORE_CONTRIBUTIONS_MULTIPLIER = 3


@dataclass
class UserStatus:
    """Enumeration of user status levels based on account age."""
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"


def _get_user_status(days_active: float) -> str:
    """Determine user status based on account age in days."""
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    elif days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW


def _calculate_score(points: float, contributions: int) -> float:
    """Calculate user engagement score."""
    return points * SCORE_POINTS_MULTIPLIER + contributions * SCORE_CONTRIBUTIONS_MULTIPLIER


def _format_report_line(name: str, status: str, email: str, 
                        days_active: float, score: float, format: str) -> str:
    """Format a single user report line based on requested format."""
    if format == "summary":
        return f"{name} ({status}) - Score: {score:.0f}"
    elif format == "detail":
        return f"{name} <{email}> | Status: {status} | Days: {days_active:.0f} | Score: {score:.0f}"
    else:  # "name" or other
        return name


def _fetch_user_data(user_id: int, cache: dict) -> Optional[dict]:
    """Fetch user data from API with caching and error handling."""
    if user_id in cache:
        return cache[user_id]
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/{user_id}",
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        cache[user_id] = data
        return data
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch user {user_id}: {e}")
        return None
    except ValueError as e:
        logger.warning(f"Invalid JSON response for user {user_id}: {e}")
        return None


def _validate_user_data(data: dict) -> bool:
    """Validate that user data has required fields."""
    required_fields = {"first", "last", "contact", "created_ts", "points", "contributions"}
    if not all(field in data for field in required_fields):
        return False
    if "email" not in data.get("contact", {}):
        return False
    return True


def get_user_report(user_ids: list[int], format: str = "summary", cache: Optional[dict] = None) -> str:
    """
    Generate a report of user information.
    
    Args:
        user_ids: List of user IDs to fetch
        format: Output format - "summary", "detail", or "name"
        cache: Optional cache dict (defaults to new dict per call)
    
    Returns:
        Formatted report string with header and user lines
    """
    if cache is None:
        cache = {}
    
    results = []
    
    for user_id in user_ids:
        data = _fetch_user_data(user_id, cache)
        if data is None:
            continue
        
        if not _validate_user_data(data):
            logger.warning(f"User {user_id} missing required fields")
            continue
        
        # Extract and calculate user metrics
        name = f"{data['first']} {data['last']}"
        email = data["contact"]["email"]
        days_active = (datetime.now().timestamp() - data["created_ts"]) / SECONDS_PER_DAY
        status = _get_user_status(days_active)
        score = _calculate_score(data["points"], data["contributions"])
        
        line = _format_report_line(name, status, email, days_active, score, format)
        results.append(line)
    
    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(results)

# Single call
report = get_user_report([123, 456, 789])

# Reuse cache across multiple calls
shared_cache = {}
report1 = get_user_report([1, 2, 3], cache=shared_cache)
report2 = get_user_report([4, 5, 6], cache=shared_cache)  # Reuses cached data