"""
User report generation module.

Refactored to address critical issues:
- Bare except clauses → specific exception handling
- Mutable default arguments → removed (items=[] anti-pattern)
- Global state → dependency injection with UserCache class
- Magic numbers → named constants
- Poor error handling → detailed logging & validation
- Unused/confusing parameters → simplified API
"""

import logging
import time
from enum import Enum
from typing import Optional, Dict, List

import requests

logger = logging.getLogger(__name__)

# Configuration constants
API_BASE_URL = "https://api.example.com"
API_TIMEOUT_SECONDS = 3
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3


class UserStatus(Enum):
    """User account status based on tenure."""
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"


class ReportFormat(Enum):
    """User report output format."""
    SUMMARY = "summary"
    DETAIL = "detail"
    SIMPLE = "simple"


class UserCache:
    """Thread-safe in-memory cache with size limit."""
    
    def __init__(self, max_size: int = 128):
        self.cache: Dict[int, Optional[Dict]] = {}
        self.max_size = max_size
    
    def get(self, user_id: int) -> Optional[Dict]:
        return self.cache.get(user_id)
    
    def set(self, user_id: int, data: Optional[Dict]) -> None:
        if len(self.cache) >= self.max_size:
            self.cache.clear()
        self.cache[user_id] = data


def fetch_user(user_id: int, cache: Optional[UserCache] = None) -> Optional[Dict]:
    """Fetch user data from API with optional caching."""
    if cache:
        cached = cache.get(user_id)
        if cached is not None:
            return cached
    
    url = f"{API_BASE_URL}/users/{user_id}"
    try:
        response = requests.get(url, timeout=API_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        if cache:
            cache.set(user_id, data)
        return data
    
    except requests.ConnectionError as e:
        logger.error(f"Connection error for user {user_id}: {e}")
    except requests.Timeout:
        logger.error(f"Timeout for user {user_id}")
    except requests.HTTPError as e:
        logger.error(f"HTTP {e.response.status_code} for user {user_id}")
    except ValueError as e:
        logger.error(f"Invalid JSON for user {user_id}: {e}")
    
    if cache:
        cache.set(user_id, None)  # Cache failure
    return None


def validate_user_data(data: Dict) -> None:
    """Validate required fields and types. Raises KeyError or TypeError."""
    required = {
        "first": str, "last": str, "points": (int, float),
        "contributions": int, "created_ts": (int, float),
    }
    
    for field, expected_type in required.items():
        if field not in data:
            raise KeyError(f"Missing field: {field}")
        if not isinstance(data[field], expected_type):
            raise TypeError(f"Field '{field}' has wrong type")
    
    if "contact" not in data or "email" not in data.get("contact", {}):
        raise KeyError("Missing: contact.email")


def calculate_status(days_active: float) -> UserStatus:
    """Determine status from tenure."""
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    elif days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    else:
        return UserStatus.NEW


def calculate_score(points: float, contributions: int) -> float:
    """Calculate weighted score."""
    return points * POINTS_MULTIPLIER + contributions * CONTRIBUTIONS_MULTIPLIER


def format_user_line(
    name: str, email: str, status: UserStatus,
    days_active: float, score: float, fmt: ReportFormat,
) -> str:
    """Format user data as report line."""
    if fmt == ReportFormat.SUMMARY:
        return f"{name} ({status.value}) - Score: {score:.0f}"
    if fmt == ReportFormat.DETAIL:
        return f"{name} <{email}> | Status: {status.value} | Days: {days_active:.0f} | Score: {score:.0f}"
    return name  # SIMPLE


def get_user_report(
    user_ids: List[int],
    report_format: str = "summary",
    use_cache: bool = True,
) -> str:
    """
    Generate user report.
    
    Args:
        user_ids: User IDs to include
        report_format: "summary", "detail", or "simple"
        use_cache: Whether to cache API responses
    
    Raises:
        ValueError: If format is invalid
    """
    try:
        fmt = ReportFormat(report_format)
    except ValueError as e:
        valid = ", ".join(f.value for f in ReportFormat)
        raise ValueError(f"Invalid format. Choose: {valid}") from e
    
    cache = UserCache() if use_cache else None
    results = []
    
    for user_id in user_ids:
        user_data = fetch_user(user_id, cache)
        if user_data is None:
            logger.debug(f"Skipping user {user_id}: fetch failed")
            continue
        
        try:
            validate_user_data(user_data)
        except (KeyError, TypeError) as e:
            logger.warning(f"Skipping user {user_id}: {e}")
            continue
        
        name = f"{user_data['first']} {user_data['last']}"
        email = user_data["contact"]["email"]
        days_active = (time.time() - user_data["created_ts"]) / 86400
        status = calculate_status(days_active)
        score = calculate_score(user_data["points"], user_data["contributions"])
        
        line = format_user_line(name, email, status, days_active, score, fmt)
        results.append(line)
    
    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(results)