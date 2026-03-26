import requests
import json
import logging
import time
from typing import TypedDict, Literal
from dataclasses import dataclass
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# Constants (replace magic numbers)
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30


class UserData(TypedDict):
    """Expected structure from API response."""
    first: str
    last: str
    contact: dict
    created_ts: float
    points: float
    contributions: int


FormatType = Literal["summary", "detail", "name"]


@dataclass
class UserInfo:
    """Structured user information for consistent formatting."""
    name: str
    email: str
    status: str
    days_active: float
    score: float

    def format(self, fmt: FormatType) -> str:
        """Format user info according to specified format."""
        formatters = {
            "summary": lambda u: f"{u.name} ({u.status}) - Score: {u.score:.0f}",
            "detail": lambda u: (
                f"{u.name} <{u.email}> | Status: {u.status} | "
                f"Days: {u.days_active:.0f} | Score: {u.score:.0f}"
            ),
            "name": lambda u: u.name,
        }
        if fmt not in formatters:
            raise ValueError(f"Unknown format: {fmt}")
        return formatters[fmt](self)


class UserReportGenerator:
    """Generate user reports with caching and error handling."""

    def __init__(self, api_base_url: str = API_BASE_URL, timeout: int = REQUEST_TIMEOUT):
        self.api_base_url = api_base_url
        self.timeout = timeout
        self._cache: dict[int, UserData] = {}

    def _fetch_user(self, user_id: int) -> UserData | None:
        """Fetch user data from API with caching."""
        if user_id in self._cache:
            return self._cache[user_id]

        try:
            url = urljoin(self.api_base_url, f"/users/{user_id}")
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            self._cache[user_id] = data
            return data
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch user {user_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response for user {user_id}: {e}")
            return None

    def _get_status(self, days_active: float) -> str:
        """Determine user status based on days active."""
        if days_active > VETERAN_THRESHOLD_DAYS:
            return "veteran"
        elif days_active > REGULAR_THRESHOLD_DAYS:
            return "regular"
        return "new"

    def _calculate_score(self, points: float, contributions: int) -> float:
        """Calculate user score. Points weighted 1.5x, contributions 3x."""
        return points * 1.5 + contributions * 3

    def _extract_user_info(self, data: UserData) -> UserInfo | None:
        """Extract and validate user information from API data."""
        try:
            name = f"{data['first']} {data['last']}"
            email = data["contact"]["email"]
            days_active = (time.time() - data["created_ts"]) / SECONDS_PER_DAY
            status = self._get_status(days_active)
            score = self._calculate_score(data["points"], data["contributions"])

            return UserInfo(
                name=name,
                email=email,
                status=status,
                days_active=days_active,
                score=score,
            )
        except KeyError as e:
            logger.error(f"Missing required field in user data: {e}")
            return None

    def generate_report(
        self, user_ids: list[int], fmt: FormatType = "summary"
    ) -> str:
        """Generate a formatted report for the given user IDs."""
        if not user_ids:
            return ""

        lines = []
        for user_id in user_ids:
            data = self._fetch_user(user_id)
            if data is None:
                continue

            user_info = self._extract_user_info(data)
            if user_info is None:
                continue

            lines.append(user_info.format(fmt))

        if not lines:
            return "No valid users found."

        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        return header + "\n" + "\n".join(lines)


# Backwards-compatible function interface
def get_user_report(
    user_ids: list[int], format: FormatType = "summary"
) -> str:
    """Generate user report (legacy function interface)."""
    generator = UserReportGenerator()
    return generator.generate_report(user_ids, format)