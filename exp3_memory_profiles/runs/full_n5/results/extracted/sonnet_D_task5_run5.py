from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

# ── Constants ──────────────────────────────────────────────────────────────
API_BASE = "https://api.example.com"
REQUEST_TIMEOUT_S = 3
SECONDS_PER_DAY = 86_400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
POINTS_WEIGHT = 1.5
CONTRIBUTIONS_WEIGHT = 3.0
REPORT_HEADER = "=" * 40 + "\nUSER REPORT\n" + "=" * 40


# ── Domain types ───────────────────────────────────────────────────────────
class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"

class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    MINIMAL = "minimal"


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
        return (time.time() - self.created_ts) / SECONDS_PER_DAY

    @property
    def status(self) -> UserStatus:
        days = self.days_active
        if days > VETERAN_THRESHOLD_DAYS:
            return UserStatus.VETERAN
        if days > REGULAR_THRESHOLD_DAYS:
            return UserStatus.REGULAR
        return UserStatus.NEW

    @property
    def score(self) -> float:
        return self.points * POINTS_WEIGHT + self.contributions * CONTRIBUTIONS_WEIGHT

    @classmethod
    def from_api_response(cls, uid: int, payload: dict) -> "UserRecord":
        return cls(
            uid=uid,
            first_name=payload["first"],
            last_name=payload["last"],
            email=payload["contact"]["email"],
            created_ts=payload["created_ts"],
            points=payload["points"],
            contributions=payload["contributions"],
        )


# ── Fetch layer ────────────────────────────────────────────────────────────
_cache: dict[int, UserRecord] = {}

def _fetch_user(uid: int, session: requests.Session) -> Optional[UserRecord]:
    if uid in _cache:
        return _cache[uid]
    resp = session.get(f"{API_BASE}/users/{uid}", timeout=REQUEST_TIMEOUT_S)
    resp.raise_for_status()          # 4xx/5xx → HTTPError, not cached
    record = UserRecord.from_api_response(uid, resp.json())
    _cache[uid] = record
    return record

def _fetch_user_safe(uid: int, session: requests.Session) -> Optional[UserRecord]:
    """
    TODO: Implement your fetch error handling strategy here (~5-10 lines).

    This is the key architectural decision — how failures propagate affects
    correctness of any downstream aggregate stats.

    Three approaches:

      A) Fail-fast: re-raise. Caller knows immediately. Good when a missing
         user is always a bug (batch ETL, compliance reports).

      B) Skip + log: return None. Silent omission — downstream totals will
         drift with no signal. Only safe if callers check len(results).

      C) Partial results + error collection: change signature to
         tuple[list[UserRecord], list[FetchError]]. Most honest for pipelines
         where partial data is expected (e.g., eventually-consistent sources).

    Distinguish `HTTPError` (404 = user gone vs 500 = infra down) from
    `ConnectionError`/`Timeout` — they have different retry semantics.
    """
    try:
        return _fetch_user(uid, session)
    except (requests.HTTPError, requests.ConnectionError, requests.Timeout):
        return None  # ← replace with your strategy


# ── Format layer ───────────────────────────────────────────────────────────
def _format_line(record: UserRecord, fmt: ReportFormat) -> str:
    match fmt:
        case ReportFormat.SUMMARY:
            return f"{record.full_name} ({record.status.value}) - Score: {record.score:.0f}"
        case ReportFormat.DETAIL:
            return (
                f"{record.full_name} <{record.email}> | "
                f"Status: {record.status.value} | "
                f"Days: {record.days_active:.0f} | "
                f"Score: {record.score:.0f}"
            )
        case ReportFormat.MINIMAL:
            return record.full_name


# ── Public API ─────────────────────────────────────────────────────────────
def get_user_report(
    user_ids: list[int],
    fmt: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    lines: list[str] = []
    with requests.Session() as session:
        for uid in user_ids:
            record = _fetch_user_safe(uid, session)
            if record is not None:
                lines.append(_format_line(record, fmt))
    return REPORT_HEADER + "\n" + "\n".join(lines)