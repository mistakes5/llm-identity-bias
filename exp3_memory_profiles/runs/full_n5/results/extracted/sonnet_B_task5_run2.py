"""
user_report.py — Fetch users from the API and produce a formatted report.

Architecture
────────────
  UserRecord         — pure data class; no I/O, fully testable
  UserStatus         — enum for the three account-age buckets
  ReportFormat       — enum for the three output layouts
  UserCache          — thin dict wrapper; injectable in tests
  fetch_user()       — single-user HTTP fetch with explicit error handling
  format_user_line() — pure formatting; no I/O
  get_user_report()  — orchestrates the above; returns a report string
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT_S = 3

SECONDS_PER_DAY = 86_400

VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30

SCORE_POINTS_WEIGHT = 1.5
SCORE_CONTRIBUTIONS_WEIGHT = 3.0

REPORT_SEPARATOR = "=" * 40


# ── Enums ────────────────────────────────────────────────────────────────────

class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW     = "new"


class ReportFormat(str, Enum):
    SUMMARY   = "summary"
    DETAIL    = "detail"
    NAME_ONLY = "name_only"


# ── Data model ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class UserRecord:
    uid: int
    first_name: str
    last_name: str
    email: str
    created_ts: float
    points: float
    contributions: float

    @classmethod
    def from_api_response(cls, uid: int, payload: dict) -> "UserRecord":
        """
        Parse a raw API dict into a UserRecord.
        Raises KeyError if required fields are absent — callers handle this
        explicitly rather than silently producing broken records.
        """
        return cls(
            uid=uid,
            first_name=payload["first"],
            last_name=payload["last"],
            email=payload["contact"]["email"],
            created_ts=float(payload["created_ts"]),
            points=float(payload["points"]),
            contributions=float(payload["contributions"]),
        )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def days_active(self, now: Optional[float] = None) -> float:
        """Account age in days. `now` is injectable for deterministic tests."""
        reference = now if now is not None else time.time()
        return (reference - self.created_ts) / SECONDS_PER_DAY

    def status(self, now: Optional[float] = None) -> UserStatus:
        age = self.days_active(now)
        if age > VETERAN_THRESHOLD_DAYS:
            return UserStatus.VETERAN
        if age > REGULAR_THRESHOLD_DAYS:
            return UserStatus.REGULAR
        return UserStatus.NEW

    @property
    def score(self) -> float:
        return (
            self.points * SCORE_POINTS_WEIGHT
            + self.contributions * SCORE_CONTRIBUTIONS_WEIGHT
        )


# ── Cache ─────────────────────────────────────────────────────────────────────

class UserCache:
    """
    Simple in-memory user record cache.
    Pass a fresh instance in tests to prevent cross-test contamination.
    """

    def __init__(self) -> None:
        self._store: dict[int, UserRecord] = {}

    def get(self, uid: int) -> Optional[UserRecord]:
        return self._store.get(uid)

    def set(self, uid: int, record: UserRecord) -> None:
        self._store[uid] = record

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


_default_cache = UserCache()  # module-level default; replace in tests


# ── HTTP layer ────────────────────────────────────────────────────────────────

def fetch_user(
    uid: int,
    *,
    cache: UserCache = _default_cache,
    base_url: str = BASE_URL,
) -> Optional[UserRecord]:
    """
    Return a UserRecord for `uid`, consulting the cache first.
    Returns None (with a warning) on any fetch or parse failure.
    """
    cached = cache.get(uid)
    if cached is not None:
        return cached

    url = f"{base_url}/users/{uid}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_S)
        resp.raise_for_status()                     # surfaces 4xx / 5xx
        record = UserRecord.from_api_response(uid, resp.json())
        cache.set(uid, record)
        return record

    except requests.HTTPError as exc:
        logger.warning("HTTP error fetching user %s: %s", uid, exc)
    except requests.RequestException as exc:
        logger.warning("Network error fetching user %s: %s", uid, exc)
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Unexpected response shape for user %s: %s", uid, exc)

    return None


# ── Formatting ────────────────────────────────────────────────────────────────

def format_user_line(record: UserRecord, fmt: ReportFormat) -> str:
    """Pure function: render one UserRecord as a report line."""
    status = record.status()

    if fmt == ReportFormat.SUMMARY:
        return f"{record.full_name} ({status.value}) - Score: {record.score:.0f}"

    if fmt == ReportFormat.DETAIL:
        return (
            f"{record.full_name} <{record.email}> | "
            f"Status: {status.value} | "
            f"Days: {record.days_active():.0f} | "
            f"Score: {record.score:.0f}"
        )

    return record.full_name  # ReportFormat.NAME_ONLY


# ── Public API ────────────────────────────────────────────────────────────────

def get_user_report(
    user_ids: list[int],
    fmt: ReportFormat = ReportFormat.SUMMARY,
    *,
    cache: UserCache = _default_cache,
    base_url: str = BASE_URL,
) -> str:
    """
    Fetch each user in `user_ids` and return a formatted report string.
    Users that cannot be fetched are skipped; the function never raises on
    partial failures.
    """
    lines: list[str] = []

    for uid in user_ids:
        record = fetch_user(uid, cache=cache, base_url=base_url)
        if record is None:
            logger.warning("Skipping user %s — could not be fetched.", uid)
            continue
        lines.append(format_user_line(record, fmt))

    header = f"{REPORT_SEPARATOR}\nUSER REPORT\n{REPORT_SEPARATOR}"
    body   = "\n".join(lines) if lines else "(no users)"
    return f"{header}\n{body}"