from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

# ── Constants ──────────────────────────────────────────────────────────────────

_API_BASE        = "https://api.example.com"
_REQUEST_TIMEOUT = 3          # seconds
_SECS_PER_DAY    = 86_400

VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30

POINTS_WEIGHT        = 1.5
CONTRIBUTIONS_WEIGHT = 3.0

# ── Domain types ───────────────────────────────────────────────────────────────

class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW     = "new"

    @classmethod
    def from_days_active(cls, days: float) -> "UserStatus":
        if days > VETERAN_THRESHOLD_DAYS:
            return cls.VETERAN
        if days > REGULAR_THRESHOLD_DAYS:
            return cls.REGULAR
        return cls.NEW


class ReportFormat(str, Enum):
    SUMMARY  = "summary"
    DETAIL   = "detail"
    NAME_ONLY = "name"


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
        return (time.time() - self.created_ts) / _SECS_PER_DAY

    @property
    def status(self) -> UserStatus:
        return UserStatus.from_days_active(self.days_active)

    @property
    def score(self) -> float:
        # TODO — see contribution request below
        raise NotImplementedError


# ── Cache (module-level, private) ──────────────────────────────────────────────

_cache: dict[int, UserRecord] = {}


def _fetch_user(uid: int) -> Optional[UserRecord]:
    """Fetch one user from the API (or return the cached copy). Returns None on error."""
    if uid in _cache:
        return _cache[uid]

    try:
        resp = requests.get(f"{_API_BASE}/users/{uid}", timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()          # raises HTTPError for 4xx/5xx
        raw = resp.json()
    except requests.RequestException as exc:
        print(f"[warn] Could not fetch user {uid}: {exc}")
        return None

    record = UserRecord(
        uid=uid,
        first_name=raw["first"],
        last_name=raw["last"],
        email=raw["contact"]["email"],
        created_ts=raw["created_ts"],
        points=raw["points"],
        contributions=raw["contributions"],
    )
    _cache[uid] = record
    return record


# ── Formatting ─────────────────────────────────────────────────────────────────

def _format_line(user: UserRecord, fmt: ReportFormat) -> str:
    if fmt == ReportFormat.DETAIL:
        return (
            f"{user.full_name} <{user.email}> | "
            f"Status: {user.status.value} | "
            f"Days: {user.days_active:.0f} | "
            f"Score: {user.score:.0f}"
        )
    if fmt == ReportFormat.SUMMARY:
        return f"{user.full_name} ({user.status.value}) - Score: {user.score:.0f}"
    return user.full_name


# ── Public API ─────────────────────────────────────────────────────────────────

def get_user_report(
    user_ids: list[int],
    fmt: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """
    Fetch users by ID and return a formatted report string.

    Args:
        user_ids: IDs of users to include.
        fmt:      Output format — SUMMARY, DETAIL, or NAME_ONLY.

    Returns:
        A multi-line report. Users that could not be fetched are silently skipped.
    """
    lines = [
        _format_line(user, fmt)
        for uid in user_ids
        if (user := _fetch_user(uid)) is not None
    ]

    sep    = "=" * 40
    header = f"{sep}\nUSER REPORT\n{sep}"
    body   = "\n".join(lines) if lines else "(no users fetched)"
    return f"{header}\n{body}"

@property
def score(self) -> float:
    # Your implementation here (~2–4 lines)
    ...