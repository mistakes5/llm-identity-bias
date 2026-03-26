from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import requests

# ── Constants ─────────────────────────────────────────────────
_BASE_URL = "https://api.example.com/users"
_REQUEST_TIMEOUT_S = 3

_SECS_PER_DAY = 86_400
_VETERAN_THRESHOLD_DAYS = 365
_REGULAR_THRESHOLD_DAYS = 30

_POINTS_WEIGHT = 1.5
_CONTRIBUTIONS_WEIGHT = 3.0

_REPORT_HEADER = "=" * 40 + "\nUSER REPORT\n" + "=" * 40

_cache: dict[int, dict] = {}


# ── Domain types ───────────────────────────────────────────────
class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name"


class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"


@dataclass(frozen=True)
class UserEntry:
    name: str
    email: str
    days_active: float
    score: float
    status: UserStatus

    def render(self, fmt: ReportFormat) -> str:
        match fmt:
            case ReportFormat.SUMMARY:
                return f"{self.name} ({self.status.value}) - Score: {self.score:.0f}"
            case ReportFormat.DETAIL:
                return (
                    f"{self.name} <{self.email}> | Status: {self.status.value}"
                    f" | Days: {self.days_active:.0f} | Score: {self.score:.0f}"
                )
            case _:
                return self.name


# ── Internal helpers ───────────────────────────────────────────
def _fetch_user(uid: int) -> dict | None:
    """Returns raw API payload, or None on any transport/HTTP error."""
    if uid in _cache:
        return _cache[uid]
    try:
        resp = requests.get(f"{_BASE_URL}/{uid}", timeout=_REQUEST_TIMEOUT_S)
        resp.raise_for_status()
        data: dict = resp.json()
        _cache[uid] = data
        return data
    except requests.RequestException:
        return None  # caller decides how to handle missing users


def _classify_status(days_active: float) -> UserStatus:
    if days_active > _VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    if days_active > _REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW


def _compute_score(points: int, contributions: int) -> float:
    # TODO: your scoring formula — see contribution request below
    return points * _POINTS_WEIGHT + contributions * _CONTRIBUTIONS_WEIGHT


def _build_entry(data: dict) -> UserEntry:
    days_active = (time.time() - data["created_ts"]) / _SECS_PER_DAY
    return UserEntry(
        name=f"{data['first']} {data['last']}",
        email=data["contact"]["email"],
        days_active=days_active,
        score=_compute_score(data["points"], data["contributions"]),
        status=_classify_status(days_active),
    )


# ── Public API ─────────────────────────────────────────────────
def get_user_report(
    user_ids: Sequence[int],
    fmt: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    lines: list[str] = []
    for uid in user_ids:
        data = _fetch_user(uid)
        if data is None:
            continue
        lines.append(_build_entry(data).render(fmt))
    return _REPORT_HEADER + "\n" + "\n".join(lines)