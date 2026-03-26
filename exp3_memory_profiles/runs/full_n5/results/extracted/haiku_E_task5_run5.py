import requests
import json
import time
from typing import List, Optional
from dataclasses import dataclass

# Define constants at the top (replaces magic numbers)
SECONDS_PER_DAY = 86400
VETERAN_DAYS = 365
REGULAR_DAYS = 30
SCORE_POINTS_MULTIPLIER = 1.5
SCORE_CONTRIBUTIONS_MULTIPLIER = 3
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3


@dataclass
class UserData:
    """Holds validated user information."""
    name: str
    email: str
    status: str
    days_active: float
    score: float


class UserReportGenerator:
    """Generates formatted user reports with caching and error handling."""

    def __init__(self, cache_expiry_hours: int = 24):
        # Cache stores (data, timestamp) tuples for expiry support
        self._cache = {}
        self._cache_expiry_seconds = cache_expiry_hours * 3600

    def _is_cache_valid(self, uid: str) -> bool:
        """Check if cached data exists and hasn't expired."""
        if uid not in self._cache:
            return False

        data, timestamp = self._cache[uid]
        age = time.time() - timestamp
        return age < self._cache_expiry_seconds

    def _fetch_user_data(self, user_id: int) -> Optional[dict]:
        """
        Fetch user data from API. Returns None if request fails.
        Logs specific errors instead of silencing them.
        """
        try:
            url = f"{API_BASE_URL}/users/{user_id}"
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()  # Raise error for bad status codes
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching user {user_id}: {e}")
            return None

    def _calculate_status(self, days_active: float) -> str:
        """Determine user status based on account age."""
        if days_active > VETERAN_DAYS:
            return "veteran"
        elif days_active > REGULAR_DAYS:
            return "regular"
        else:
            return "new"

    def _parse_user_data(self, raw_data: dict, user_id: int) -> Optional[UserData]:
        """
        Extract and validate user information from API response.
        Uses .get() to safely access potentially missing fields.
        """
        try:
            first_name = raw_data.get("first", "Unknown")
            last_name = raw_data.get("last", "Unknown")
            name = f"{first_name} {last_name}"

            contact = raw_data.get("contact", {})
            email = contact.get("email", "No email")

            created_ts = raw_data.get("created_ts")
            if created_ts is None:
                print(f"Missing created_ts for user {user_id}")
                return None

            days_active = (time.time() - created_ts) / SECONDS_PER_DAY
            status = self._calculate_status(days_active)

            points = raw_data.get("points", 0)
            contributions = raw_data.get("contributions", 0)
            score = (points * SCORE_POINTS_MULTIPLIER +
                    contributions * SCORE_CONTRIBUTIONS_MULTIPLIER)

            return UserData(
                name=name,
                email=email,
                status=status,
                days_active=days_active,
                score=score
            )
        except (KeyError, TypeError) as e:
            print(f"Error parsing user data for {user_id}: {e}")
            return None

    def _format_user_line(self, user: UserData, format_type: str) -> str:
        """Format user data according to requested format."""
        if format_type == "summary":
            return f"{user.name} ({user.status}) - Score: {user.score:.0f}"
        elif format_type == "detail":
            return (f"{user.name} <{user.email}> | Status: {user.status} | "
                   f"Days: {user.days_active:.0f} | Score: {user.score:.0f}")
        elif format_type == "name":
            return user.name
        else:
            raise ValueError(f"Unknown format type: {format_type}")

    def get_user_report(
        self,
        user_ids: List[int],
        format_type: str = "summary"
    ) -> str:
        """
        Generate a formatted report for the given user IDs.

        Args:
            user_ids: List of user IDs to fetch
            format_type: Output format ("summary", "detail", or "name")

        Returns:
            Formatted report as a string
        """
        if not user_ids:
            return "No users to report on"

        if format_type not in ("summary", "detail", "name"):
            raise ValueError(f"Invalid format: {format_type}")

        results = []

        for uid in user_ids:
            # Try cached data first
            if self._is_cache_valid(uid):
                raw_data, _ = self._cache[uid]
            else:
                raw_data = self._fetch_user_data(uid)
                if raw_data is None:
                    continue
                self._cache[uid] = (raw_data, time.time())

            user = self._parse_user_data(raw_data, uid)
            if user is None:
                continue

            line = self._format_user_line(user, format_type)
            results.append(line)

        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        return header + "\n" + "\n".join(results) if results else header + "\nNo valid users found"