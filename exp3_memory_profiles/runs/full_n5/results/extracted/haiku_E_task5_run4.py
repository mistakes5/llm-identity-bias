import requests
import json
import time
import logging
from typing import List, Dict, Any

# Set up logging for better error tracking
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== CONSTANTS (instead of magic numbers scattered in code) =====
SECONDS_PER_DAY = 86400
DAYS_VETERAN = 365
DAYS_REGULAR = 30
SCORE_POINTS_MULTIPLIER = 1.5
SCORE_CONTRIBUTIONS_MULTIPLIER = 3
API_TIMEOUT = 3
API_BASE_URL = "https://api.example.com"

# Format types as constants
FORMAT_SUMMARY = "summary"
FORMAT_DETAIL = "detail"
FORMAT_NAME_ONLY = "name"
VALID_FORMATS = {FORMAT_SUMMARY, FORMAT_DETAIL, FORMAT_NAME_ONLY}


class UserReportGenerator:
    """Generates formatted user reports with caching."""

    def __init__(self):
        # Cache is now an instance variable, not global
        # This makes it testable and doesn't persist between instances
        self._cache: Dict[int, Dict[str, Any]] = {}

    def _fetch_user_data(self, user_id: int) -> Dict[str, Any] | None:
        """Fetch user data from the API. Returns None if the request fails."""
        try:
            url = f"{API_BASE_URL}/users/{user_id}"
            response = requests.get(url, timeout=API_TIMEOUT)
            response.raise_for_status()  # Raise exception for bad status codes
            return response.json()

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching user {user_id}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"API error for user {user_id}: {e}")
            return None
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from API for user {user_id}")
            return None

    def _get_user_data(self, user_id: int) -> Dict[str, Any] | None:
        """Get user data from cache or fetch from API."""
        if user_id in self._cache:
            return self._cache[user_id]

        data = self._fetch_user_data(user_id)
        if data:
            self._cache[user_id] = data
        return data

    def _extract_user_info(self, user_data: Dict[str, Any]) -> Dict[str, Any] | None:
        """Extract and validate required user information from API response."""
        try:
            name = f"{user_data['first']} {user_data['last']}"
            email = user_data['contact']['email']
            created_ts = user_data['created_ts']
            points = user_data['points']
            contributions = user_data['contributions']

            days_active = (time.time() - created_ts) / SECONDS_PER_DAY
            status = self._calculate_status(days_active)
            score = points * SCORE_POINTS_MULTIPLIER + contributions * SCORE_CONTRIBUTIONS_MULTIPLIER

            return {
                'name': name,
                'email': email,
                'status': status,
                'days_active': days_active,
                'score': score
            }

        except KeyError as e:
            logger.error(f"Missing required field in user data: {e}")
            return None

    def _calculate_status(self, days_active: float) -> str:
        """Calculate user status based on days active."""
        if days_active > DAYS_VETERAN:
            return "veteran"
        elif days_active > DAYS_REGULAR:
            return "regular"
        else:
            return "new"

    def _format_user_line(self, user_info: Dict[str, Any], format_type: str) -> str:
        """Format a single user's information as a string."""
        name = user_info['name']

        if format_type == FORMAT_SUMMARY:
            return f"{name} ({user_info['status']}) - Score: {user_info['score']:.0f}"
        elif format_type == FORMAT_DETAIL:
            return (
                f"{name} <{user_info['email']}> | "
                f"Status: {user_info['status']} | "
                f"Days: {user_info['days_active']:.0f} | "
                f"Score: {user_info['score']:.0f}"
            )
        elif format_type == FORMAT_NAME_ONLY:
            return name
        else:
            raise ValueError(f"Unknown format type: {format_type}")

    def get_user_report(self, user_ids: List[int], format: str = FORMAT_SUMMARY) -> str:
        """Generate a formatted report for multiple users."""
        # Validate the format parameter
        if format not in VALID_FORMATS:
            raise ValueError(f"Invalid format '{format}'. Must be one of: {VALID_FORMATS}")

        if not user_ids:
            logger.warning("No user IDs provided")
            return self._format_header()

        results = []

        for user_id in user_ids:
            # Validate user_id
            if not isinstance(user_id, int):
                logger.warning(f"Skipping invalid user ID: {user_id}")
                continue

            user_data = self._get_user_data(user_id)
            if not user_data:
                continue

            user_info = self._extract_user_info(user_data)
            if not user_info:
                continue

            formatted_line = self._format_user_line(user_info, format)
            results.append(formatted_line)

        return self._format_header() + "\n" + "\n".join(results)

    def _format_header(self) -> str:
        """Create the report header."""
        border = "=" * 40
        return f"{border}\nUSER REPORT\n{border}"