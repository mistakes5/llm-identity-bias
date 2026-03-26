import requests
import json
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# ============================================================================
# CONSTANTS - Named values instead of "magic numbers" sprinkled in code
# ============================================================================
API_BASE_URL = "https://api.example.com"
API_TIMEOUT = 5  # seconds (3 was quite strict)

# Status thresholds (in days)
DAYS_TO_VETERAN = 365
DAYS_TO_REGULAR = 30

# Score calculation multipliers
POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3

SECONDS_PER_DAY = 86400

# ============================================================================
# DATA CLASSES - Makes the data structure explicit and type-safe
# ============================================================================
@dataclass
class UserData:
    """Represents a user's information after processing."""
    name: str
    email: str
    days_active: float
    score: float
    status: str


# ============================================================================
# HELPER FUNCTIONS - Separated concerns make code easier to test
# ============================================================================

def _calculate_status(days_active: float) -> str:
    """Determine user status based on how long they've been active."""
    if days_active > DAYS_TO_VETERAN:
        return "veteran"
    elif days_active > DAYS_TO_REGULAR:
        return "regular"
    else:
        return "new"


def _fetch_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch user data from the API with proper error handling.
    Returns None if the request fails (instead of silently continuing).
    """
    try:
        url = f"{API_BASE_URL}/users/{user_id}"
        response = requests.get(url, timeout=API_TIMEOUT)
        response.raise_for_status()  # Raises error for 4xx/5xx responses
        return response.json()
    except requests.exceptions.RequestException as e:
        # Print the actual error instead of silently failing
        print(f"Warning: Failed to fetch user {user_id}: {e}")
        return None


def _extract_user_info(raw_data: Dict[str, Any]) -> Optional[UserData]:
    """
    Extract and validate user information from API response.
    Returns None if required fields are missing.
    """
    try:
        # Use .get() to safely access nested data
        first_name = raw_data.get("first", "").strip()
        last_name = raw_data.get("last", "").strip()

        if not first_name or not last_name:
            print("Warning: Missing name fields")
            return None

        name = f"{first_name} {last_name}"
        email = raw_data.get("contact", {}).get("email", "unknown")

        # Calculate days active
        created_ts = raw_data.get("created_ts", time.time())
        days_active = (time.time() - created_ts) / SECONDS_PER_DAY

        # Calculate score
        points = raw_data.get("points", 0)
        contributions = raw_data.get("contributions", 0)
        score = points * POINTS_MULTIPLIER + contributions * CONTRIBUTIONS_MULTIPLIER

        # Determine status
        status = _calculate_status(days_active)

        return UserData(
            name=name,
            email=email,
            days_active=days_active,
            score=score,
            status=status
        )
    except (KeyError, TypeError) as e:
        print(f"Warning: Error extracting user info: {e}")
        return None


def _format_user_line(user: UserData, format_type: str = "summary") -> str:
    """Format a single user's information."""
    if format_type == "summary":
        return f"{user.name} ({user.status}) - Score: {user.score:.0f}"
    elif format_type == "detail":
        return (
            f"{user.name} <{user.email}> | Status: {user.status} | "
            f"Days: {user.days_active:.0f} | Score: {user.score:.0f}"
        )
    else:
        return user.name


def get_user_report(
    user_ids: List[int],
    format: str = "summary",
    cache: Optional[Dict[int, Dict[str, Any]]] = None
) -> str:
    """
    Generate a formatted report of user information.
    
    Args:
        user_ids: List of user IDs to fetch
        format: Output format ("summary", "detail", or "simple")
        cache: Optional dict to cache API responses (fixes mutable default!)
    """
    # FIX: Mutable default argument problem solved
    if cache is None:
        cache = {}

    results = []

    for user_id in user_ids:
        # Check cache first
        if user_id in cache:
            raw_data = cache[user_id]
        else:
            # Fetch from API
            raw_data = _fetch_user_data(user_id)
            
            if raw_data is None:
                continue  # Skip this user
            
            cache[user_id] = raw_data

        # Extract and validate
        user_info = _extract_user_info(raw_data)
        if user_info is None:
            continue

        # Format and add to results
        formatted_line = _format_user_line(user_info, format)
        results.append(formatted_line)

    # Create report
    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    
    if results:
        return header + "\n" + "\n".join(results)
    else:
        return header + "\n(No valid user data found)"