import requests
import logging
import time
from typing import Literal
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Configuration constants
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3
CACHE_MAX_SIZE = 1000
SECONDS_PER_DAY = 86400

# User status thresholds (in days)
VETERAN_THRESHOLD = 365
REGULAR_THRESHOLD = 30

# Scoring weights
POINTS_WEIGHT = 1.5
CONTRIBUTIONS_WEIGHT = 3

# Report formatting
REPORT_WIDTH = 40


class UserCache:
    """Simple cache with size limits to prevent memory bloat."""

    def __init__(self, max_size: int = CACHE_MAX_SIZE):
        self._data = {}
        self.max_size = max_size

    def get(self, user_id: int):
        return self._data.get(user_id)

    def set(self, user_id: int, data: dict) -> None:
        # Evict oldest entry when at capacity (FIFO)
        if len(self._data) >= self.max_size:
            oldest_key = next(iter(self._data))
            del self._data[oldest_key]
        self._data[user_id] = data


@dataclass
class UserProfile:
    """Encapsulates computed user attributes."""
    name: str
    email: str
    status: Literal["new", "regular", "veteran"]
    days_active: float
    score: float

    @classmethod
    def from_api_response(cls, api_data: dict) -> "UserProfile":
        """Construct profile from API response data."""
        name = f"{api_data['first']} {api_data['last']}"
        email = api_data["contact"]["email"]

        days_active = (time.time() - api_data["created_ts"]) / SECONDS_PER_DAY
        if days_active > VETERAN_THRESHOLD:
            status = "veteran"
        elif days_active > REGULAR_THRESHOLD:
            status = "regular"
        else:
            status = "new"

        score = api_data["points"] * POINTS_WEIGHT + api_data["contributions"] * CONTRIBUTIONS_WEIGHT

        return cls(name=name, email=email, status=status, days_active=days_active, score=score)

    def format(self, style: Literal["summary", "detail", "name"]) -> str:
        """Format profile according to specified style."""
        if style == "summary":
            return f"{self.name} ({self.status}) - Score: {self.score:.0f}"
        elif style == "detail":
            return f"{self.name} <{self.email}> | Status: {self.status} | Days: {self.days_active:.0f} | Score: {self.score:.0f}"
        else:  # "name"
            return self.name


def fetch_user_data(user_id: int, cache: UserCache) -> dict | None:
    """Fetch user data from API with caching and proper error handling."""
    cached = cache.get(user_id)
    if cached is not None:
        return cached

    try:
        response = requests.get(f"{API_BASE_URL}/users/{user_id}", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        cache.set(user_id, data)
        return data
    except requests.Timeout:
        logger.warning(f"Timeout fetching user {user_id}")
        return None
    except requests.HTTPError as e:
        logger.warning(f"HTTP error for user {user_id}: {e.response.status_code}")
        return None
    except requests.RequestException as e:
        logger.warning(f"Network error fetching user {user_id}: {e}")
        return None


def get_user_report(
    user_ids: list[int],
    format: Literal["summary", "detail", "name"] = "summary",
    cache: UserCache | None = None
) -> str:
    """Generate a formatted report for specified users."""
    if cache is None:
        cache = UserCache()

    profiles = []
    for user_id in user_ids:
        api_data = fetch_user_data(user_id, cache)
        if api_data is None:
            continue

        try:
            profile = UserProfile.from_api_response(api_data)
            profiles.append(profile.format(format))
        except KeyError as e:
            logger.warning(f"Missing required field for user {user_id}: {e}")
            continue

    header = "=" * REPORT_WIDTH + "\nUSER REPORT\n" + "=" * REPORT_WIDTH
    return header + "\n" + "\n".join(profiles)