"""
Refactored user report generator with improved quality.
"""
import json
import logging
from typing import Optional
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

# Configuration constants (not magic numbers)
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3
SECONDS_PER_DAY = 86400
STATUS_THRESHOLDS = {"veteran": 365, "regular": 30, "new": 0}
SCORE_MULTIPLIERS = {"points": 1.5, "contributions": 3}


@dataclass
class UserData:
    """Structured user data with computed properties."""
    first_name: str
    last_name: str
    email: str
    days_active: float
    score: float

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def status(self) -> str:
        if self.days_active >= STATUS_THRESHOLDS["veteran"]:
            return "veteran"
        elif self.days_active >= STATUS_THRESHOLDS["regular"]:
            return "regular"
        return "new"


class UserReportGenerator:
    """Class-based design eliminates global state."""

    def __init__(self, cache: Optional[dict] = None):
        self.cache = cache if cache is not None else {}
        self.session = requests.Session()  # Connection pooling

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.session.close()

    def _fetch_user_data(self, user_id: int) -> Optional[dict]:
        """Specific exception handling; returns None gracefully."""
        if user_id in self.cache:
            return self.cache[user_id]

        try:
            url = f"{API_BASE_URL}/users/{user_id}"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            self.cache[user_id] = data
            return data
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch user {user_id}: {e}")
            return None

    def _parse_user_data(self, raw_data: dict, current_time: float) -> Optional[UserData]:
        """Validates all required fields; returns None if incomplete."""
        try:
            days_active = (current_time - raw_data["created_ts"]) / SECONDS_PER_DAY
            score = (
                raw_data["points"] * SCORE_MULTIPLIERS["points"]
                + raw_data["contributions"] * SCORE_MULTIPLIERS["contributions"]
            )
            return UserData(
                first_name=raw_data["first"],
                last_name=raw_data["last"],
                email=raw_data["contact"]["email"],
                days_active=max(0, days_active),
                score=score,
            )
        except KeyError as e:
            logger.error(f"Missing field: {e}")
            return None

    def generate_report(self, user_ids: list[int], format: str = "summary") -> str:
        """No mutable default args; returns result without side effects."""
        import time
        current_time = time.time()
        results = []

        for user_id in user_ids:
            raw_data = self._fetch_user_data(user_id)
            if not raw_data:
                continue

            user = self._parse_user_data(raw_data, current_time)
            if not user:
                continue

            if format == "summary":
                line = f"{user.full_name} ({user.status}) - Score: {user.score:.0f}"
            elif format == "detail":
                line = f"{user.full_name} <{user.email}> | Status: {user.status} | Days: {user.days_active:.0f} | Score: {user.score:.0f}"
            else:
                line = user.full_name

            results.append(line)

        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        return header + "\n" + "\n".join(results)

with UserReportGenerator() as gen:
    report = gen.generate_report([1, 2, 3], format="detail")
    print(report)