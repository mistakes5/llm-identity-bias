from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests

# Constants extracted from magic numbers
API_BASE_URL = "https://api.example.com"
API_TIMEOUT_SECONDS = 3
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
SCORE_POINTS_MULTIPLIER = 1.5
SCORE_CONTRIBUTIONS_MULTIPLIER = 3
REPORT_LINE_WIDTH = 40

# Configuration for the cache with TTL
CACHE_TTL_SECONDS = 3600  # 1 hour


@dataclass
class UserData:
    """Validates and stores user API response data."""
    first_name: str
    last_name: str
    email: str
    created_ts: float
    points: float
    contributions: float

    @classmethod
    def from_api_response(cls, data: dict) -> "UserData":
        """Parse and validate API response, raising KeyError with helpful message."""
        try:
            return cls(
                first_name=data["first"],
                last_name=data["last"],
                email=data["contact"]["email"],
                created_ts=data["created_ts"],
                points=data["points"],
                contributions=data["contributions"],
            )
        except KeyError as e:
            raise ValueError(f"Missing required field in API response: {e}")


class UserCache:
    """Simple cache with TTL to prevent unbounded growth."""
    
    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self.data: dict[int, tuple[UserData, float]] = {}  # user_id -> (data, timestamp)

    def get(self, user_id: int) -> Optional[UserData]:
        if user_id not in self.data:
            return None
        
        user_data, timestamp = self.data[user_id]
        if datetime.now().timestamp() - timestamp > self.ttl_seconds:
            del self.data[user_id]
            return None
        
        return user_data

    def set(self, user_id: int, user_data: UserData) -> None:
        self.data[user_id] = (user_data, datetime.now().timestamp())


def calculate_user_status(days_active: float) -> str:
    """Determine user status based on account age."""
    if days_active > VETERAN_THRESHOLD_DAYS:
        return "veteran"
    elif days_active > REGULAR_THRESHOLD_DAYS:
        return "regular"
    return "new"


def calculate_user_score(points: float, contributions: float) -> float:
    """Calculate user score from weighted metrics."""
    return points * SCORE_POINTS_MULTIPLIER + contributions * SCORE_CONTRIBUTIONS_MULTIPLIER


def fetch_user_data(user_id: int, cache: UserCache) -> Optional[UserData]:
    """Fetch user data from API, using cache if available."""
    cached = cache.get(user_id)
    if cached:
        return cached

    try:
        url = f"{API_BASE_URL}/users/{user_id}"
        response = requests.get(url, timeout=API_TIMEOUT_SECONDS)
        response.raise_for_status()  # Raise exception for bad status codes
        user_data = UserData.from_api_response(response.json())
        cache.set(user_id, user_data)
        return user_data
    except requests.RequestException as e:
        print(f"Failed to fetch user {user_id}: {e}")
        return None
    except ValueError as e:
        print(f"Invalid user data for {user_id}: {e}")
        return None


def format_user_line(user_data: UserData, status: str, days_active: float, score: float, format: str) -> str:
    """Format a single user line according to the requested format."""
    name = f"{user_data.first_name} {user_data.last_name}"
    
    if format == "summary":
        return f"{name} ({status}) - Score: {score:.0f}"
    elif format == "detail":
        return f"{name} <{user_data.email}> | Status: {status} | Days: {days_active:.0f} | Score: {score:.0f}"
    else:  # format == "name"
        return name


def get_user_report(user_ids: list[int], format: str = "summary") -> str:
    """
    Generate a report for multiple users.
    
    Args:
        user_ids: List of user IDs to include in report
        format: Output format - "summary", "detail", or "name"
    
    Returns:
        Formatted user report as string
    """
    if not user_ids:
        return ""

    cache = UserCache()  # Create a fresh cache per report (no unbounded global state)
    results = []

    for user_id in user_ids:
        user_data = fetch_user_data(user_id, cache)
        if not user_data:
            continue

        days_active = (datetime.now().timestamp() - user_data.created_ts) / SECONDS_PER_DAY
        status = calculate_user_status(days_active)
        score = calculate_user_score(user_data.points, user_data.contributions)
        
        line = format_user_line(user_data, status, days_active, score, format)
        results.append(line)

    if not results:
        return "No users found."

    header = "=" * REPORT_LINE_WIDTH + "\nUSER REPORT\n" + "=" * REPORT_LINE_WIDTH
    return header + "\n" + "\n".join(results)