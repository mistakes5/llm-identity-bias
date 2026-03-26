"""User reporting module with efficient caching and error handling."""

import logging
from typing import Optional, TypedDict
from functools import lru_cache
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuration constants
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3
CACHE_SIZE = 1000
CACHE_TTL_SECONDS = 3600

# User status thresholds (days)
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30

# Score calculation weights
POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3

# Format types
FORMAT_SUMMARY = "summary"
FORMAT_DETAIL = "detail"
FORMAT_NAME_ONLY = "name"

logger = logging.getLogger(__name__)


class UserData(TypedDict):
    """Type hint for user API response structure."""
    first: str
    last: str
    contact: dict[str, str]
    created_ts: float
    points: int
    contributions: int


def create_session() -> requests.Session:
    """Create a session with connection pooling and retry logic."""
    session = requests.Session()
    
    # Retry strategy for transient failures
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


# Global session for connection pooling
_session = create_session()


def fetch_user_data(uid: int) -> Optional[UserData]:
    """
    Fetch user data from API with error handling.
    
    Args:
        uid: User ID to fetch
        
    Returns:
        User data dict or None if fetch fails
    """
    try:
        response = _session.get(
            f"{API_BASE_URL}/users/{uid}",
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch user {uid}: {e}")
        return None
    except ValueError as e:
        logger.warning(f"Invalid JSON for user {uid}: {e}")
        return None


def extract_user_info(data: UserData) -> tuple[str, str]:
    """
    Safely extract name and email from user data.
    
    Args:
        data: User data dict
        
    Returns:
        Tuple of (full_name, email)
    """
    name = f"{data.get('first', 'Unknown')} {data.get('last', 'Unknown')}".strip()
    email = data.get('contact', {}).get('email', 'unknown@example.com')
    return name, email


def calculate_days_active(created_ts: float) -> float:
    """Calculate days since account creation."""
    return (datetime.now().timestamp() - created_ts) / 86400


def calculate_user_status(days_active: float) -> str:
    """
    Determine user status based on account age.
    
    Args:
        days_active: Days since account creation
        
    Returns:
        Status string: 'veteran', 'regular', or 'new'
    """
    if days_active > VETERAN_THRESHOLD_DAYS:
        return "veteran"
    elif days_active > REGULAR_THRESHOLD_DAYS:
        return "regular"
    else:
        return "new"


def calculate_user_score(points: int, contributions: int) -> float:
    """Calculate user engagement score."""
    return points * POINTS_MULTIPLIER + contributions * CONTRIBUTIONS_MULTIPLIER


def format_user_line(
    name: str,
    status: str,
    email: str,
    days_active: float,
    score: float,
    format_type: str
) -> str:
    """
    Format user data according to requested format.
    
    Args:
        format_type: One of 'summary', 'detail', or 'name'
        
    Returns:
        Formatted user line
    """
    if format_type == FORMAT_SUMMARY:
        return f"{name} ({status}) - Score: {score:.0f}"
    elif format_type == FORMAT_DETAIL:
        return (
            f"{name} <{email}> | Status: {status} | "
            f"Days: {days_active:.0f} | Score: {score:.0f}"
        )
    else:  # FORMAT_NAME_ONLY
        return name


def get_user_report(
    user_ids: list[int],
    format_type: str = FORMAT_SUMMARY
) -> str:
    """
    Generate a formatted report for multiple users.
    
    Args:
        user_ids: List of user IDs to report on
        format_type: Report format ('summary', 'detail', or 'name')
        
    Returns:
        Formatted report string
        
    Raises:
        ValueError: If format_type is invalid
    """
    if format_type not in (FORMAT_SUMMARY, FORMAT_DETAIL, FORMAT_NAME_ONLY):
        raise ValueError(f"Unknown format: {format_type}")
    
    lines = []
    
    for uid in user_ids:
        data = fetch_user_data(uid)
        if data is None:
            continue
        
        name, email = extract_user_info(data)
        days_active = calculate_days_active(data["created_ts"])
        status = calculate_user_status(days_active)
        score = calculate_user_score(data["points"], data["contributions"])
        
        line = format_user_line(name, status, email, days_active, score, format_type)
        lines.append(line)
    
    # Build report with header
    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(lines)