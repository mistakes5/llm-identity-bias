from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)

# Configuration constants
SECONDS_PER_DAY = 86400
VETERAN_DAYS_THRESHOLD = 365
REGULAR_DAYS_THRESHOLD = 30
REQUEST_TIMEOUT = 3
API_BASE_URL = "https://api.example.com"

@dataclass
class UserProfile:
    """Immutable user profile with all relevant fields."""
    name: str
    email: str
    days_active: float
    status: str
    score: float

class UserCache:
    """Simple in-memory cache with clear interface."""
    def __init__(self):
        self._cache = {}
    
    def get(self, user_id: int) -> Optional[dict]:
        return self._cache.get(user_id)
    
    def set(self, user_id: int, data: dict) -> None:
        self._cache[user_id] = data

def create_session() -> requests.Session:
    """Create a requests session with exponential backoff retry strategy."""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def fetch_user_data(user_id: int, session: requests.Session, cache: UserCache) -> Optional[dict]:
    """Fetch user data from API or return cached version.
    
    Returns None if fetch fails; logs the error.
    """
    if (cached := cache.get(user_id)) is not None:
        return cached
    
    try:
        resp = session.get(f"{API_BASE_URL}/users/{user_id}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        cache.set(user_id, data)
        return data
    except requests.RequestException as e:
        logger.error(f"Failed to fetch user {user_id}: {e}")
        return None

def calculate_status(days_active: float) -> str:
    """Determine user status based on account age (days).
    
    TODO: Verify these thresholds with product team.
    Consider: should these be configurable?
    """
    if days_active > VETERAN_DAYS_THRESHOLD:
        return "veteran"
    elif days_active > REGULAR_DAYS_THRESHOLD:
        return "regular"
    return "new"

def calculate_score(user_data: dict) -> float:
    """Calculate user engagement score.
    
    TODO: Implement your scoring formula.
    Current formula: points * 1.5 + contributions * 3
    
    Consider:
    - What do these multipliers represent?
    - Should score be normalized (0-100)?
    - Are there edge cases (negative values, nulls)?
    """
    points = user_data.get("points", 0)
    contributions = user_data.get("contributions", 0)
    return points * 1.5 + contributions * 3

def extract_profile(user_data: dict) -> Optional[UserProfile]:
    """Extract and validate user profile from API response.
    
    Returns None if required fields are missing or malformed.
    """
    try:
        name = f"{user_data['first']} {user_data['last']}"
        email = user_data["contact"]["email"]
        days_active = (datetime.now().timestamp() - user_data["created_ts"]) / SECONDS_PER_DAY
        status = calculate_status(days_active)
        score = calculate_score(user_data)
        
        return UserProfile(
            name=name,
            email=email,
            days_active=days_active,
            status=status,
            score=score
        )
    except (KeyError, TypeError) as e:
        logger.warning(f"Invalid user data structure: {e}")
        return None

def format_profile(profile: UserProfile, format: str = "summary") -> str:
    """Format a user profile for display."""
    if format == "summary":
        return f"{profile.name} ({profile.status}) - Score: {profile.score:.0f}"
    elif format == "detail":
        return (
            f"{profile.name} <{profile.email}> | Status: {profile.status} | "
            f"Days: {profile.days_active:.0f} | Score: {profile.score:.0f}"
        )
    return profile.name

def get_user_report(user_ids: list[int], format: str = "summary") -> str:
    """Generate a formatted report for multiple users.
    
    Args:
        user_ids: List of user IDs to include in the report
        format: Output format ('summary', 'detail', or 'names')
    
    Returns:
        Formatted report string
    """
    cache = UserCache()
    session = create_session()
    results = []
    
    try:
        for user_id in user_ids:
            user_data = fetch_user_data(user_id, session, cache)
            if user_data is None:
                continue
            
            profile = extract_profile(user_data)
            if profile is None:
                continue
            
            results.append(format_profile(profile, format))
    finally:
        session.close()  # Ensure session is always closed
    
    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    body = "\n".join(results) if results else "(No users found)"
    return f"{header}\n{body}"