import logging
from typing import Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_API_TIMEOUT = 3
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
SCORE_POINTS_MULTIPLIER = 1.5
SCORE_CONTRIBUTIONS_MULTIPLIER = 3

@dataclass
class UserStatus:
    name: str
    email: str
    status: str  # "new", "regular", "veteran"
    days_active: float
    score: float

    def format_summary(self) -> str:
        return f"{self.name} ({self.status}) - Score: {self.score:.0f}"

    def format_detail(self) -> str:
        return f"{self.name} <{self.email}> | Status: {self.status} | Days: {self.days_active:.0f} | Score: {self.score:.0f}"

    def format_simple(self) -> str:
        return self.name


class UserReportCache:
    """Thread-safe cache with explicit lifecycle."""
    def __init__(self):
        self._cache: dict[int, dict[str, Any]] = {}

    def get(self, user_id: int) -> Optional[dict[str, Any]]:
        return self._cache.get(user_id)

    def set(self, user_id: int, data: dict[str, Any]) -> None:
        self._cache[user_id] = data

    def clear(self) -> None:
        self._cache.clear()


def _fetch_user_data(user_id: int, cache: UserReportCache, timeout: int = DEFAULT_API_TIMEOUT) -> Optional[dict[str, Any]]:
    """Fetch user data from API, with caching."""
    cached = cache.get(user_id)
    if cached:
        return cached

    try:
        response = requests.get(
            f"https://api.example.com/users/{user_id}",
            timeout=timeout
        )
        response.raise_for_status()
        data = response.json()
        cache.set(user_id, data)
        return data
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch user {user_id}: {e}")
        return None
    except ValueError as e:
        logger.error(f"Invalid JSON response for user {user_id}: {e}")
        return None


def _calculate_status(days_active: float) -> str:
    """Determine user status based on days active."""
    if days_active > VETERAN_THRESHOLD_DAYS:
        return "veteran"
    elif days_active > REGULAR_THRESHOLD_DAYS:
        return "regular"
    return "new"


def _build_user_status(data: dict[str, Any]) -> Optional[UserStatus]:
    """Extract and validate user data into UserStatus object."""
    try:
        name = f"{data['first']} {data['last']}"
        email = data['contact']['email']
        days_active = (datetime.now().timestamp() - data['created_ts']) / 86400
        status = _calculate_status(days_active)
        score = data['points'] * SCORE_POINTS_MULTIPLIER + data['contributions'] * SCORE_CONTRIBUTIONS_MULTIPLIER
        
        return UserStatus(name, email, status, days_active, score)
    except KeyError as e:
        logger.error(f"Missing required field: {e}")
        return None


def get_user_report(
    user_ids: list[int],
    format: str = "summary",
    cache: Optional[UserReportCache] = None,
    timeout: int = DEFAULT_API_TIMEOUT
) -> str:
    """Generate a formatted report of users.
    
    Args:
        user_ids: List of user IDs to fetch
        format: Output format ("summary", "detail", or "simple")
        cache: Optional cache instance (creates new if not provided)
        timeout: API request timeout in seconds
        
    Returns:
        Formatted report string
    """
    if cache is None:
        cache = UserReportCache()

    if format not in ("summary", "detail", "simple"):
        raise ValueError(f"Unknown format: {format}")

    results = []
    for user_id in user_ids:
        data = _fetch_user_data(user_id, cache, timeout)
        if data is None:
            continue

        user_status = _build_user_status(data)
        if user_status is None:
            continue

        if format == "summary":
            line = user_status.format_summary()
        elif format == "detail":
            line = user_status.format_detail()
        else:  # simple
            line = user_status.format_simple()

        results.append(line)

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(results)