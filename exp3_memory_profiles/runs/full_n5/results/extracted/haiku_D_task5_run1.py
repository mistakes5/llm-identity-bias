import requests
import logging
from dataclasses import dataclass
from typing import Optional, Literal
from datetime import datetime, timedelta

# Constants
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
API_TIMEOUT_SECS = 3
SCORE_MULTIPLIER_POINTS = 1.5
SCORE_MULTIPLIER_CONTRIBUTIONS = 3

logger = logging.getLogger(__name__)


@dataclass
class UserData:
    """Parsed user data with validation."""
    first: str
    last: str
    email: str
    created_ts: float
    points: float
    contributions: float

    @classmethod
    def from_api(cls, data: dict) -> "UserData":
        """Safely extract and validate user data from API response."""
        try:
            return cls(
                first=data["first"],
                last=data["last"],
                email=data["contact"]["email"],
                created_ts=data["created_ts"],
                points=float(data.get("points", 0)),
                contributions=float(data.get("contributions", 0)),
            )
        except KeyError as e:
            raise ValueError(f"Missing required field in API response: {e}")


class UserCache:
    """Simple in-memory cache. Can be replaced with Redis/Memcached."""
    def __init__(self):
        self._data = {}

    def get(self, key: str) -> Optional[dict]:
        return self._data.get(key)

    def set(self, key: str, value: dict) -> None:
        self._data[key] = value


def _classify_user_status(days_active: float) -> str:
    """Determine user status based on account age."""
    if days_active > VETERAN_THRESHOLD_DAYS:
        return "veteran"
    elif days_active > REGULAR_THRESHOLD_DAYS:
        return "regular"
    return "new"


def _calculate_score(points: float, contributions: float) -> float:
    """Compute user engagement score."""
    return points * SCORE_MULTIPLIER_POINTS + contributions * SCORE_MULTIPLIER_CONTRIBUTIONS


def _format_user_line(
    user_data: UserData,
    status: str,
    days_active: float,
    format: Literal["summary", "detail", "name"] = "summary",
) -> str:
    """Format a single user line based on the requested format."""
    name = f"{user_data.first} {user_data.last}"
    score = _calculate_score(user_data.points, user_data.contributions)

    if format == "detail":
        return f"{name} <{user_data.email}> | Status: {status} | Days: {days_active:.0f} | Score: {score:.0f}"
    elif format == "summary":
        return f"{name} ({status}) - Score: {score:.0f}"
    else:  # "name"
        return name


def get_user_report(
    user_ids: list[str],
    format: Literal["summary", "detail", "name"] = "summary",
    cache: Optional[UserCache] = None,
) -> str:
    """
    Generate a report for multiple users.
    
    Args:
        user_ids: List of user IDs to fetch
        format: Output format ("summary", "detail", or "name")
        cache: Optional cache instance (defaults to new instance per call)
    
    Returns:
        Formatted report string
    
    Raises:
        ValueError: If a user's data is malformed or unreachable
    """
    if cache is None:
        cache = UserCache()

    results = []
    current_time = datetime.now().timestamp()

    for uid in user_ids:
        # Fetch from cache or API
        raw_data = cache.get(uid)
        if raw_data is None:
            try:
                resp = requests.get(
                    f"https://api.example.com/users/{uid}",
                    timeout=API_TIMEOUT_SECS,
                )
                resp.raise_for_status()
                raw_data = resp.json()
                cache.set(uid, raw_data)
            except requests.RequestException as e:
                logger.error(f"Failed to fetch user {uid}: {e}")
                continue
            except ValueError as e:
                logger.error(f"Invalid JSON for user {uid}: {e}")
                continue

        # Parse and validate
        try:
            user_data = UserData.from_api(raw_data)
        except ValueError as e:
            logger.error(f"Invalid user data for {uid}: {e}")
            continue

        # Calculate metrics
        days_active = (current_time - user_data.created_ts) / SECONDS_PER_DAY
        status = _classify_user_status(days_active)
        
        # Format output
        line = _format_user_line(user_data, status, days_active, format)
        results.append(line)

    # Build report
    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(results)