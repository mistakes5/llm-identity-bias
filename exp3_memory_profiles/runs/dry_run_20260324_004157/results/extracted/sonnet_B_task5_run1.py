from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
API_BASE_URL = "https://api.example.com/users"
REQUEST_TIMEOUT = 3

DAYS_VETERAN = 365
DAYS_REGULAR = 30
SECONDS_PER_DAY = 86_400

SCORE_POINTS_WEIGHT = 1.5
SCORE_CONTRIBUTIONS_WEIGHT = 3.0

REPORT_DIVIDER = "=" * 40


# ── Domain types ──────────────────────────────────────────────────────────────
class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME = "name"


@dataclass(frozen=True)
class User:
    first: str
    last: str
    email: str
    created_ts: float
    points: int
    contributions: int

    @classmethod
    def from_api_response(cls, payload: dict) -> User:
        return cls(
            first=payload["first"],
            last=payload["last"],
            email=payload["contact"]["email"],
            created_ts=payload["created_ts"],
            points=payload["points"],
            contributions=payload["contributions"],
        )

    # ── Derived properties ─────────────────────────────────────────────────
    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"

    @property
    def days_active(self) -> float:
        return (time.time() - self.created_ts) / SECONDS_PER_DAY

    @property
    def account_status(self) -> str:
        if self.days_active > DAYS_VETERAN:
            return "veteran"
        if self.days_active > DAYS_REGULAR:
            return "regular"
        return "new"

    @property
    def score(self) -> float:
        return (
            self.points * SCORE_POINTS_WEIGHT
            + self.contributions * SCORE_CONTRIBUTIONS_WEIGHT
        )


# ── Fetch layer ───────────────────────────────────────────────────────────────
_cache: dict[int, User] = {}  # TODO: add TTL — see contribution prompt below


def _fetch_user(user_id: int) -> Optional[User]:
    """Fetch one user from the API. Returns None on network or parse failure."""
    try:
        resp = requests.get(f"{API_BASE_URL}/{user_id}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return User.from_api_response(resp.json())
    except requests.RequestException as exc:
        logger.warning("Network error fetching user %s: %s", user_id, exc)
        return None
    except (KeyError, ValueError) as exc:
        logger.warning("Malformed response for user %s: %s", user_id, exc)
        return None


def _get_user(user_id: int) -> Optional[User]:
    """Return from cache, or fetch and populate cache."""
    if user_id not in _cache:
        user = _fetch_user(user_id)
        if user is None:
            return None
        _cache[user_id] = user
    return _cache[user_id]


# ── Format layer ──────────────────────────────────────────────────────────────
def _format_line(user: User, fmt: ReportFormat) -> str:
    if fmt == ReportFormat.SUMMARY:
        return f"{user.full_name} ({user.account_status}) - Score: {user.score:.0f}"
    if fmt == ReportFormat.DETAIL:
        return (
            f"{user.full_name} <{user.email}> | "
            f"Status: {user.account_status} | "
            f"Days: {user.days_active:.0f} | "
            f"Score: {user.score:.0f}"
        )
    return user.full_name


# ── Public API ─────────────────────────────────────────────────────────────────
def get_user_report(
    user_ids: list[int],
    report_format: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """Return a formatted report for the given user IDs.

    Users that cannot be fetched are silently skipped.
    """
    lines = [
        _format_line(user, report_format)
        for uid in user_ids
        if (user := _get_user(uid)) is not None
    ]

    header = f"{REPORT_DIVIDER}\nUSER REPORT\n{REPORT_DIVIDER}"
    return header + "\n" + "\n".join(lines)

# _get_user() — current logic
if user_id not in _cache:
    user = _fetch_user(user_id)
    if user is None:
        return None
    _cache[user_id] = user
return _cache[user_id]