# user_report.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import requests

# ── Constants ──────────────────────────────────────────────────────────────────
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT_SECONDS = 3

SCORE_POINTS_MULTIPLIER = 1.5
SCORE_CONTRIBUTIONS_MULTIPLIER = 3.0

VETERAN_DAYS_THRESHOLD = 365
REGULAR_DAYS_THRESHOLD = 30

REPORT_SEPARATOR = "=" * 40


# ── Domain types ───────────────────────────────────────────────────────────────
class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"


class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name_only"


@dataclass(frozen=True)
class UserRecord:
    uid: int
    first_name: str
    last_name: str
    email: str
    created_ts: float
    points: int
    contributions: int

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def days_active(self) -> float:
        return (time.time() - self.created_ts) / 86400

    @property
    def status(self) -> UserStatus:
        if self.days_active > VETERAN_DAYS_THRESHOLD:
            return UserStatus.VETERAN
        if self.days_active > REGULAR_DAYS_THRESHOLD:
            return UserStatus.REGULAR
        return UserStatus.NEW

    @property
    def score(self) -> float:
        return (
            self.points * SCORE_POINTS_MULTIPLIER
            + self.contributions * SCORE_CONTRIBUTIONS_MULTIPLIER
        )


# ── Cache (in-process) ─────────────────────────────────────────────────────────
@dataclass
class CacheEntry:
    record: UserRecord
    fetched_at: float = field(default_factory=time.time)

    def is_stale(self, ttl_seconds: float) -> bool:
        # TODO: implement your staleness policy here (5-10 lines)
        # Trade-offs to consider:
        #   - Short TTL (e.g. 300s): fresher data, more API calls under load
        #   - Long TTL (e.g. 86400s): fewer calls, but profile changes go unnoticed
        #   - TTL of 0 / math.inf: effectively "no cache" or "cache forever"
        # Return True if this entry should be re-fetched, False to serve as-is.
        raise NotImplementedError


_cache: dict[int, CacheEntry] = {}
CACHE_TTL_SECONDS = 300.0  # adjust to taste


# ── Fetching ───────────────────────────────────────────────────────────────────
def _parse_user(uid: int, raw: dict) -> UserRecord:
    return UserRecord(
        uid=uid,
        first_name=raw["first"],
        last_name=raw["last"],
        email=raw["contact"]["email"],
        created_ts=float(raw["created_ts"]),
        points=int(raw["points"]),
        contributions=int(raw["contributions"]),
    )


def _fetch_user(uid: int) -> Optional[UserRecord]:
    """Fetch a single user from the API. Returns None on any failure."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/users/{uid}",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return _parse_user(uid, resp.json())
    except requests.RequestException as exc:
        print(f"[warn] Network error fetching user {uid}: {exc}")
        return None
    except (KeyError, ValueError) as exc:
        print(f"[warn] Unexpected API shape for user {uid}: {exc}")
        return None


def _get_user(uid: int) -> Optional[UserRecord]:
    """Return a UserRecord, using the in-process cache."""
    entry = _cache.get(uid)
    if entry is None or entry.is_stale(CACHE_TTL_SECONDS):
        user = _fetch_user(uid)
        if user is None:
            return None
        _cache[uid] = CacheEntry(record=user)
    return _cache[uid].record


# ── Formatting ─────────────────────────────────────────────────────────────────
def _format_line(user: UserRecord, report_format: ReportFormat) -> str:
    if report_format == ReportFormat.DETAIL:
        return (
            f"{user.full_name} <{user.email}> | "
            f"Status: {user.status.value} | "
            f"Days: {user.days_active:.0f} | "
            f"Score: {user.score:.0f}"
        )
    if report_format == ReportFormat.SUMMARY:
        return f"{user.full_name} ({user.status.value}) - Score: {user.score:.0f}"
    return user.full_name  # NAME_ONLY


# ── Public API ─────────────────────────────────────────────────────────────────
def get_user_report(
    user_ids: list[int],
    report_format: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """
    Build a formatted user report for the given IDs.

    Users that cannot be fetched are silently skipped.
    Results are cached in-process; configure CACHE_TTL_SECONDS to control freshness.
    """
    lines = [
        _format_line(user, report_format)
        for uid in user_ids
        if (user := _get_user(uid)) is not None
    ]

    header = f"{REPORT_SEPARATOR}\nUSER REPORT\n{REPORT_SEPARATOR}"
    return header + "\n" + "\n".join(lines)

def is_stale(self, ttl_seconds: float) -> bool:
    # implement here — ~2 lines