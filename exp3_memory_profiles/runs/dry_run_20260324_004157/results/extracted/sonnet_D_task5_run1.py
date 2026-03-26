from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Final

import requests

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
SECONDS_PER_DAY: Final = 86_400
VETERAN_THRESHOLD_DAYS: Final = 365
REGULAR_THRESHOLD_DAYS: Final = 30
POINTS_MULTIPLIER: Final = 1.5
CONTRIBUTIONS_MULTIPLIER: Final = 3.0
API_BASE_URL: Final = "https://api.example.com/users"
REQUEST_TIMEOUT_S: Final = 3

_cache: dict[int, dict] = {}  # module-level; not thread-safe — use functools.lru_cache or a lock if concurrent


# ── Domain types ──────────────────────────────────────────────────────────────
class ReportFormat(str, Enum):
    SUMMARY  = "summary"
    DETAIL   = "detail"
    NAME_ONLY = "name_only"


class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW     = "new"


@dataclass(frozen=True)
class UserReport:
    name:        str
    email:       str
    status:      UserStatus
    days_active: float
    score:       float

    def render(self, fmt: ReportFormat) -> str:
        match fmt:
            case ReportFormat.SUMMARY:
                return f"{self.name} ({self.status.value}) - Score: {self.score:.0f}"
            case ReportFormat.DETAIL:
                return (
                    f"{self.name} <{self.email}> | Status: {self.status.value}"
                    f" | Days: {self.days_active:.0f} | Score: {self.score:.0f}"
                )
            case ReportFormat.NAME_ONLY:
                return self.name


# ── Fetch layer ───────────────────────────────────────────────────────────────
def _fetch_user(uid: int) -> dict:
    if uid in _cache:
        return _cache[uid]
    resp = requests.get(f"{API_BASE_URL}/{uid}", timeout=REQUEST_TIMEOUT_S)
    resp.raise_for_status()           # raises HTTPError on 4xx/5xx
    data: dict = resp.json()
    _cache[uid] = data
    return data


# ── Transform layer ───────────────────────────────────────────────────────────
def _classify_status(days_active: float) -> UserStatus:
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    if days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW


def _build_report(data: dict) -> UserReport:
    days_active = (time.time() - data["created_ts"]) / SECONDS_PER_DAY
    return UserReport(
        name        = f"{data['first']} {data['last']}",
        email       = data["contact"]["email"],
        status      = _classify_status(days_active),
        days_active = days_active,
        score       = data["points"] * POINTS_MULTIPLIER + data["contributions"] * CONTRIBUTIONS_MULTIPLIER,
    )


# ── Report entry point ────────────────────────────────────────────────────────
def get_user_report(
    user_ids:      list[int],
    report_format: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """
    Fetch and format a report for the given user IDs.
    Users that fail to fetch or parse are skipped with a warning log.
    """
    lines: list[str] = []

    for uid in user_ids:
        try:
            data = _fetch_user(uid)
            lines.append(_build_report(data).render(report_format))
        except requests.HTTPError as exc:
            logger.warning("HTTP error for user %d: %s", uid, exc)
        except requests.RequestException as exc:
            logger.warning("Network error for user %d: %s", uid, exc)
        except KeyError as exc:
            logger.warning("Malformed payload for user %d — missing field: %s", uid, exc)

    header = f"{'=' * 40}\nUSER REPORT\n{'=' * 40}"
    return "\n".join([header, *lines])

# TODO: implement failure reporting strategy
    # Approaches to consider:
    #   1. Collect failed IDs → raise after the loop with the full failure set
    #   2. Return (report_str, failed_ids) tuple → caller decides
    #   3. Accept an on_error: Callable[[int, Exception], None] callback
    #   4. Keep warn-and-skip, but expose a get_failed_ids() on a class wrapper
    #
    # For a pipeline feeding downstream aggregations, option 2 or 3 avoids
    # silent partial correctness — the silent skip above is appropriate only
    # if missing users are expected and acceptable.