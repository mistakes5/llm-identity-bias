# user_report.py
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

# ── Constants ─────────────────────────────────────────────────────────────────
_SECS_PER_DAY = 86_400
_VETERAN_DAYS = 365
_REGULAR_DAYS = 30
_POINTS_WEIGHT = 1.5
_CONTRIB_WEIGHT = 3.0
_API_BASE = "https://api.example.com/users"
_REPORT_HEADER = "=" * 40 + "\nUSER REPORT\n" + "=" * 40


# ── Domain types ──────────────────────────────────────────────────────────────
class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME = "name"


class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"


@dataclass(frozen=True)
class UserRecord:
    uid: int
    name: str
    email: str
    days_active: float
    status: UserStatus
    score: float


# ── Pure transform functions ───────────────────────────────────────────────────
def _classify(days: float) -> UserStatus:
    if days > _VETERAN_DAYS:
        return UserStatus.VETERAN
    if days > _REGULAR_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW


def _parse(uid: int, data: dict) -> UserRecord:
    days = (time.time() - data["created_ts"]) / _SECS_PER_DAY
    return UserRecord(
        uid=uid,
        name=f"{data['first']} {data['last']}",
        email=data["contact"]["email"],
        days_active=days,
        status=_classify(days),
        score=data["points"] * _POINTS_WEIGHT + data["contributions"] * _CONTRIB_WEIGHT,
    )


def _format(record: UserRecord, fmt: ReportFormat) -> str:
    match fmt:
        case ReportFormat.DETAIL:
            return (
                f"{record.name} <{record.email}> | "
                f"Status: {record.status.value} | "
                f"Days: {record.days_active:.0f} | "
                f"Score: {record.score:.0f}"
            )
        case ReportFormat.SUMMARY:
            return f"{record.name} ({record.status.value}) - Score: {record.score:.0f}"
        case _:
            return record.name


# ── I/O layer ─────────────────────────────────────────────────────────────────
class UserReportBuilder:
    """Fetches users and renders a formatted report.

    A single Session is reused for connection pooling.
    Cache is instance-scoped — no global state.
    """

    def __init__(self, timeout: float = 3.0) -> None:
        self._session = requests.Session()
        self._cache: dict[int, dict] = {}
        self._timeout = timeout

    def _fetch(self, uid: int) -> Optional[dict]:
        if uid in self._cache:
            return self._cache[uid]

        resp = self._session.get(f"{_API_BASE}/{uid}", timeout=self._timeout)
        resp.raise_for_status()                 # propagates HTTP 4xx/5xx
        data: dict = resp.json()
        self._cache[uid] = data
        return data

    def build(
        self,
        user_ids: list[int],
        fmt: ReportFormat = ReportFormat.SUMMARY,
    ) -> str:
        lines: list[str] = []

        for uid in user_ids:
            # TODO: implement your error handling strategy here (see below)
            data = self._fetch(uid)
            if data is None:
                continue
            lines.append(_format(_parse(uid, data), fmt))

        return _REPORT_HEADER + "\n" + "\n".join(lines)

# Option A — Fail-fast (best for batch jobs where partial output is useless)
data = self._fetch(uid)  # raises, caller handles

# Option B — Collect errors, return partial results + error manifest
errors: dict[int, Exception] = {}
try:
    data = self._fetch(uid)
except (requests.RequestException, KeyError) as exc:
    errors[uid] = exc
    continue

# Option C — Structured result type (no exceptions escape)
from typing import Union

@dataclass
class FetchError:
    uid: int
    reason: str