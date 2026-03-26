import requests
from typing import List, Dict, Optional
from functools import lru_cache
import time

# Constants
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD = 365
REGULAR_THRESHOLD = 30
POINTS_WEIGHT = 1.5
CONTRIBUTIONS_WEIGHT = 3

@lru_cache(maxsize=128)
def fetch_user_data(user_id: int) -> Optional[Dict]:
    """Fetch user data from API with automatic caching."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/users/{user_id}",
            timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"Failed to fetch user {user_id}: {e}")
        return None

def get_user_status(days_active: float) -> str:
    """Determine user status based on account age."""
    if days_active > VETERAN_THRESHOLD:
        return "veteran"
    elif days_active > REGULAR_THRESHOLD:
        return "regular"
    return "new"

def calculate_score(points: float, contributions: int) -> float:
    """Calculate user score from points and contributions."""
    return points * POINTS_WEIGHT + contributions * CONTRIBUTIONS_WEIGHT

def format_user_line(user_data: Dict, format: str = "summary") -> Optional[str]:
    """Format a single user's data according to the specified format."""
    try:
        name = f"{user_data['first']} {user_data['last']}"
        email = user_data.get("contact", {}).get("email", "N/A")
        created_ts = user_data.get("created_ts", time.time())
        points = user_data.get("points", 0)
        contributions = user_data.get("contributions", 0)

        days_active = (time.time() - created_ts) / SECONDS_PER_DAY
        status = get_user_status(days_active)
        score = calculate_score(points, contributions)

        if format == "summary":
            return f"{name} ({status}) - Score: {score:.0f}"
        elif format == "detail":
            return f"{name} <{email}> | Status: {status} | Days: {days_active:.0f} | Score: {score:.0f}"
        return name
    except (KeyError, TypeError) as e:
        print(f"Error formatting user data: {e}")
        return None

def get_user_report(user_ids: List[int], format: str = "summary") -> str:
    """Generate a report for a list of users."""
    results = []
    
    for user_id in user_ids:
        user_data = fetch_user_data(user_id)
        if user_data is None:
            continue
        
        line = format_user_line(user_data, format)
        if line:
            results.append(line)

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(results)