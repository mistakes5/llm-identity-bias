"""User report generation with caching and formatting."""

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

# Configuration constants
API_BASE_URL = "https://api.example.com"
API_TIMEOUT = 3
SECONDS_PER_DAY = 86400

# Status thresholds (days active)
VETERAN_THRESHOLD = 365
REGULAR_THRESHOLD = 30

# Scoring weights
POINTS_WEIGHT = 1.5
CONTRIBUTIONS_WEIGHT = 3


class UserStatus(Enum):
    """User activity status classification."""
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"


class ReportFormat(Enum):
    """User report output format."""
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name"


@dataclass
class UserInfo:
    """Structured user data from API."""
    user_id: int
    first_name: str
    last_name: str
    email: str
    created_ts: float
    points: float
    contributions: int

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def days_active(self) -> float:
        return (time.time() - self.created_ts) / SECONDS_PER_DAY

    @classmethod
    def from_api_response(cls, user_id: int, data: dict) -> "UserInfo":
        """Parse API response into UserInfo."""
        return cls(
            user_id=user_id,
            first_name=data["first"],
            last_name=data["last"],
            email=data["contact"]["email"],
            created_ts=data["created_ts"],
            points=data.get("points", 0),
            contributions=data.get("contributions", 0),
        )


def calculate_status(days_active: float) -> UserStatus:
    """Determine user status based on account age."""
    if days_active > VETERAN_THRESHOLD:
        return UserStatus.VETERAN
    elif days_active > REGULAR_THRESHOLD:
        return UserStatus.REGULAR
    return UserStatus.NEW


def calculate_score(points: float, contributions: int) -> float:
    """Calculate user engagement score."""
    return points * POINTS_WEIGHT + contributions * CONTRIBUTIONS_WEIGHT


def fetch_user_data(user_id: int) -> Optional[dict]:
    """Fetch user data from API with error handling."""
    try:
        url = urljoin(API_BASE_URL, f"/users/{user_id}")
        resp = requests.get(url, timeout=API_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch user {user_id}: {e}")
        return None


class UserCache:
    """In-memory cache with bounded size."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: dict[int, dict] = {}

    def get(self, user_id: int) -> Optional[dict]:
        return self._cache.get(user_id)

    def set(self, user_id: int, data: dict) -> None:
        if len(self._cache) >= self.max_size:
            del self._cache[next(iter(self._cache))]
        self._cache[user_id] = data


def format_user_line(
    user: UserInfo, status: UserStatus, score: float, format_type: ReportFormat
) -> str:
    """Format user info into a report line."""
    if format_type == ReportFormat.SUMMARY:
        return f"{user.full_name} ({status.value}) - Score: {score:.0f}"
    elif format_type == ReportFormat.DETAIL:
        return (
            f"{user.full_name} <{user.email}> | "
            f"Status: {status.value} | "
            f"Days: {user.days_active:.0f} | "
            f"Score: {score:.0f}"
        )
    return user.full_name  # NAME_ONLY


def get_user_report(
    user_ids: list[int],
    format_type: str = "summary",
    cache: Optional[UserCache] = None,
) -> str:
    """
    Generate a formatted report of user data.

    Args:
        user_ids: List of user IDs to fetch and report.
        format_type: Output format ("summary", "detail", or "name").
        cache: Optional UserCache instance.

    Returns:
        Formatted user report as a string.

    Raises:
        ValueError: If format_type is invalid.
    """
    try:
        report_format = ReportFormat(format_type)
    except ValueError:
        valid = [f.value for f in ReportFormat]
        raise ValueError(f"Invalid format_type: {format_type}. Must be one of {valid}")

    if cache is None:
        cache = UserCache()

    results = []

    for user_id in user_ids:
        cached_data = cache.get(user_id)
        data = cached_data or fetch_user_data(user_id)

        if data is None:
            logger.warning(f"Skipping user {user_id}: no data available")
            continue

        if not cached_data:
            cache.set(user_id, data)

        try:
            user = UserInfo.from_api_response(user_id, data)
            status = calculate_status(user.days_active)
            score = calculate_score(user.points, user.contributions)
            line = format_user_line(user, status, score, report_format)
            results.append(line)
        except KeyError as e:
            logger.error(f"Missing required field for user {user_id}: {e}")
            continue

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(results) if results else header + "\nNo users to report."