import logging
import time
from dataclasses import dataclass
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# Configuration constants
DAYS_PER_VETERAN = 365
DAYS_PER_REGULAR = 30
SECONDS_PER_DAY = 86400
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3

SCORE_POINTS_WEIGHT = 1.5
SCORE_CONTRIBUTION_WEIGHT = 3


@dataclass
class UserStatus:
    name: str
    email: str
    status: str
    days_active: float
    score: float


class UserCache:
    """In-memory user data cache with explicit lifecycle."""
    
    def __init__(self):
        self._data = {}
    
    def get(self, user_id: int) -> Optional[dict]:
        return self._data.get(user_id)
    
    def set(self, user_id: int, data: dict) -> None:
        self._data[user_id] = data
    
    def clear(self) -> None:
        self._data.clear()


def fetch_user(user_id: int, cache: UserCache, session: requests.Session) -> Optional[dict]:
    """Fetch user data with caching and explicit error handling."""
    cached = cache.get(user_id)
    if cached:
        return cached
    
    try:
        resp = session.get(
            f"{API_BASE_URL}/users/{user_id}",
            timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        cache.set(user_id, data)
        return data
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch user {user_id}: {e}")
        return None


def calculate_user_status(data: dict) -> UserStatus:
    """Extract and calculate user status from API response."""
    days_active = (time.time() - data["created_ts"]) / SECONDS_PER_DAY
    
    if days_active > DAYS_PER_VETERAN:
        status = "veteran"
    elif days_active > DAYS_PER_REGULAR:
        status = "regular"
    else:
        status = "new"
    
    score = (
        data["points"] * SCORE_POINTS_WEIGHT +
        data["contributions"] * SCORE_CONTRIBUTION_WEIGHT
    )
    
    return UserStatus(
        name=f"{data['first']} {data['last']}",
        email=data["contact"]["email"],
        status=status,
        days_active=days_active,
        score=score,
    )


def format_user_line(user: UserStatus, fmt: str) -> str:
    """Format user data according to requested format."""
    if fmt == "summary":
        return f"{user.name} ({user.status}) - Score: {user.score:.0f}"
    elif fmt == "detail":
        return (
            f"{user.name} <{user.email}> | Status: {user.status} | "
            f"Days: {user.days_active:.0f} | Score: {user.score:.0f}"
        )
    else:
        return user.name


def get_user_report(
    user_ids: list[int],
    format: str = "summary",
) -> str:
    """Generate user report with explicit resource management."""
    cache = UserCache()
    results = []
    
    with requests.Session() as session:
        for user_id in user_ids:
            data = fetch_user(user_id, cache, session)
            if data is None:
                continue
            
            try:
                user = calculate_user_status(data)
                line = format_user_line(user, format)
                results.append(line)
            except KeyError as e:
                logger.error(f"Invalid user data structure for {user_id}: {e}")
                continue
    
    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(results)