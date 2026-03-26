import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import requests
from requests import HTTPError, RequestException

logger = logging.getLogger(__name__)

# --- Constants ---
DAYS_VETERAN_THRESHOLD = 365
DAYS_REGULAR_THRESHOLD = 30
POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3.0
SECONDS_PER_DAY = 86_400
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3


class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name_only"


class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"


@dataclass
class UserRecord:
    uid: int
    first: str
    last: str
    email: str
    created_ts: float
    points: float
    contributions: float

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"

    @property
    def days_active(self) -> float:
        return (time.time() - self.created_ts) / SECONDS_PER_DAY

    @property
    def status(self) -> UserStatus:
        if self.days_active > DAYS_VETERAN_THRESHOLD:
            return UserStatus.VETERAN
        elif self.days_active > DAYS_REGULAR_THRESHOLD:
            return UserStatus.REGULAR
        return UserStatus.NEW

    @property
    def score(self) -> float:
        return self.points * POINTS_MULTIPLIER + self.contributions * CONTRIBUTIONS_MULTIPLIER


# --- Cache (could be replaced with functools.lru_cache or an external store) ---
_user_cache: dict[int, UserRecord] = {}


def _fetch_user(uid: int) -> Optional[UserRecord]:
    """Fetch a single user from the API, returning None on any failure."""
    url = f"{API_BASE_URL}/users/{uid}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()  # raises HTTPError for 4xx/5xx
        raw = resp.json()
        return UserRecord(
            uid=uid,
            first=raw["first"],
            last=raw["last"],
            email=raw["contact"]["email"],
            created_ts=raw["created_ts"],
            points=raw["points"],
            contributions=raw["contributions"],
        )
    except HTTPError as e:
        logger.warning("HTTP error fetching user %d: %s", uid, e)
    except RequestException as e:
        logger.warning("Network error fetching user %d: %s", uid, e)
    except (KeyError, ValueError) as e:
        logger.warning("Unexpected payload for user %d: %s", uid, e)
    return None


def _get_user(uid: int) -> Optional[UserRecord]:
    """Return a UserRecord from cache or API."""
    if uid not in _user_cache:
        user = _fetch_user(uid)
        if user is None:
            return None
        _user_cache[uid] = user
    return _user_cache[uid]


def _format_line(user: UserRecord, fmt: ReportFormat) -> str:
    """Render a single user as a report line."""
    match fmt:
        case ReportFormat.SUMMARY:
            return f"{user.full_name} ({user.status.value}) - Score: {user.score:.0f}"
        case ReportFormat.DETAIL:
            return (
                f"{user.full_name} <{user.email}> | "
                f"Status: {user.status.value} | "
                f"Days: {user.days_active:.0f} | "
                f"Score: {user.score:.0f}"
            )
        case ReportFormat.NAME_ONLY:
            return user.full_name


def get_user_report(
    user_ids: list[int],
    fmt: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """
    Fetch user data and return a formatted report string.

    Args:
        user_ids: List of user IDs to include.
        fmt:      Output format (SUMMARY, DETAIL, or NAME_ONLY).

    Returns:
        A multi-line report string. Users that cannot be fetched are skipped.
    """
    lines: list[str] = []
    for uid in user_ids:
        user = _get_user(uid)
        if user is None:
            logger.info("Skipping user %d (unavailable)", uid)
            continue
        lines.append(_format_line(user, fmt))

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(lines)