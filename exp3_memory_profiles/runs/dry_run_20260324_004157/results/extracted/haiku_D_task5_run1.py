"""User reporting system with proper error handling and separation of concerns."""

import logging
import time
from typing import Optional
from dataclasses import dataclass
from urllib.parse import urljoin
import requests
from requests.exceptions import RequestException, Timeout

logger = logging.getLogger(__name__)

# Configuration constants (easy to tune, not scattered)
API_BASE_URL = "https://api.example.com"
API_TIMEOUT = 3
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
SCORE_MULTIPLIERS = {"points": 1.5, "contributions": 3}


@dataclass
class UserData:
    """Typed user data model."""
    user_id: int
    name: str
    email: str
    days_active: float
    score: float

    @property
    def status(self) -> str:
        if self.days_active > VETERAN_THRESHOLD_DAYS:
            return "veteran"
        elif self.days_active > REGULAR_THRESHOLD_DAYS:
            return "regular"
        return "new"


class UserFetcher:
    """Handles API communication and caching (single responsibility)."""

    def __init__(self, base_url: str = API_BASE_URL, timeout: int = API_TIMEOUT, cache: Optional[dict] = None):
        self.base_url = base_url
        self.timeout = timeout
        self.cache = cache if cache is not None else {}

    def fetch_user(self, user_id: int) -> Optional[dict]:
        """Fetch single user with proper error handling."""
        if user_id in self.cache:
            return self.cache[user_id]

        try:
            url = urljoin(self.base_url, f"/users/{user_id}")
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()  # Distinguish HTTP errors
            data = resp.json()  # Cleaner than json.loads(resp.text)
            self.cache[user_id] = data
            return data
        except Timeout:
            logger.warning(f"Timeout fetching user {user_id}")
        except RequestException as e:
            logger.error(f"HTTP error for user {user_id}: {e}")
        except ValueError as e:
            logger.error(f"Invalid JSON for user {user_id}: {e}")
        return None


def parse_user_data(raw_data: dict) -> Optional[UserData]:
    """Extract and validate (no KeyError risks)."""
    try:
        first = raw_data.get("first", "")
        last = raw_data.get("last", "")
        email = raw_data.get("contact", {}).get("email", "")
        created_ts = raw_data.get("created_ts", 0)
        
        days_active = (time.time() - created_ts) / SECONDS_PER_DAY
        score = (raw_data.get("points", 0) * SCORE_MULTIPLIERS["points"] + 
                 raw_data.get("contributions", 0) * SCORE_MULTIPLIERS["contributions"])

        return UserData(
            user_id=raw_data.get("id"),
            name=f"{first} {last}".strip(),
            email=email,
            days_active=days_active,
            score=score,
        )
    except (TypeError, ValueError) as e:
        logger.warning(f"Failed to parse user data: {e}")
        return None


class UserReportFormatter:
    """Formatting logic isolated (testable, composable)."""

    @staticmethod
    def format_summary(user: UserData) -> str:
        return f"{user.name} ({user.status}) - Score: {user.score:.0f}"

    @staticmethod
    def format_detail(user: UserData) -> str:
        return (
            f"{user.name} <{user.email}> | Status: {user.status} | "
            f"Days: {user.days_active:.0f} | Score: {user.score:.0f}"
        )

    @classmethod
    def format_report(cls, users: list[UserData], format_type: str = "summary") -> str:
        """Generate report with proper header."""
        formatters = {
            "summary": cls.format_summary,
            "detail": cls.format_detail,
            "name": lambda u: u.name,
        }
        
        formatter = formatters.get(format_type, cls.format_summary)
        lines = [formatter(user) for user in users]
        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        return header + "\n" + "\n".join(lines)


def get_user_report(user_ids: list[int], format_type: str = "summary", 
                    fetcher: Optional[UserFetcher] = None) -> str:
    """Main entry point (dependency injection, no globals)."""
    if fetcher is None:
        fetcher = UserFetcher()
    
    raw_data = fetcher.fetch_users(user_ids)  # Removed weird items parameter
    users = [u for u in (parse_user_data(d) for d in raw_data) if u is not None]
    
    return UserReportFormatter.format_report(users, format_type)