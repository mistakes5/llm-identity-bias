import logging
import requests
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

# Configuration
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT_SECONDS = 3
SECONDS_PER_DAY = 86400

# User status thresholds
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30

# Score weights
POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3

logger = logging.getLogger(__name__)


class UserReportGenerator:
    """Generate reports for users from the API."""

    def __init__(self, api_base_url: str = API_BASE_URL):
        self.api_base_url = api_base_url
        self.cache: dict[int, dict] = {}

    def _fetch_user(self, user_id: int) -> Optional[dict]:
        """Fetch user data from cache or API."""
        if user_id in self.cache:
            return self.cache[user_id]

        try:
            url = urljoin(self.api_base_url, f"/users/{user_id}")
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
            self.cache[user_id] = data
            return data
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch user {user_id}: {e}")
            return None

    def _determine_status(self, days_active: float) -> str:
        """Classify user based on activity duration."""
        if days_active > VETERAN_THRESHOLD_DAYS:
            return "veteran"
        if days_active > REGULAR_THRESHOLD_DAYS:
            return "regular"
        return "new"

    def _calculate_score(self, points: float, contributions: float) -> float:
        """Weighted score calculation."""
        return points * POINTS_MULTIPLIER + contributions * CONTRIBUTIONS_MULTIPLIER

    def _extract_user_metrics(self, data: dict) -> Optional[dict]:
        """Extract and validate required fields from API response."""
        try:
            return {
                "name": f"{data['first']} {data['last']}",
                "email": data["contact"]["email"],
                "days_active": (datetime.now().timestamp() - data["created_ts"]) / SECONDS_PER_DAY,
                "points": data["points"],
                "contributions": data["contributions"],
            }
        except KeyError as e:
            logger.error(f"Missing expected field in user data: {e}")
            return None

    def _format_user_line(self, metrics: dict, format_type: str) -> str:
        """Format user info according to requested format."""
        status = self._determine_status(metrics["days_active"])
        score = self._calculate_score(metrics["points"], metrics["contributions"])

        if format_type == "summary":
            return f"{metrics['name']} ({status}) - Score: {score:.0f}"
        elif format_type == "detail":
            return (
                f"{metrics['name']} <{metrics['email']}> | "
                f"Status: {status} | Days: {metrics['days_active']:.0f} | "
                f"Score: {score:.0f}"
            )
        else:
            return metrics["name"]

    def generate_report(
        self,
        user_ids: list[int],
        format_type: str = "summary",
    ) -> str:
        """Generate a formatted report for the given users."""
        if format_type not in ("summary", "detail", "name"):
            logger.warning(f"Unknown format '{format_type}', defaulting to 'summary'")
            format_type = "summary"

        lines = []
        for user_id in user_ids:
            user_data = self._fetch_user(user_id)
            if not user_data:
                continue

            metrics = self._extract_user_metrics(user_data)
            if not metrics:
                continue

            lines.append(self._format_user_line(metrics, format_type))

        header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
        return header + "\n" + "\n".join(lines)

# Create instance and generate report
generator = UserReportGenerator()
report = generator.generate_report([123, 456, 789], format_type="detail")
print(report)