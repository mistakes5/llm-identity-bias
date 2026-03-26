from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

import requests
from requests import Session

# ---------------------------------------------------------------------------
# Constants  (no magic numbers scattered through logic)
# ---------------------------------------------------------------------------
_API_BASE               = "https://api.example.com"
_TIMEOUT_SECONDS        = 3
_SECONDS_PER_DAY        = 86_400
_VETERAN_THRESHOLD_DAYS = 365
_REGULAR_THRESHOLD_DAYS = 30
_SCORE_POINTS_WEIGHT    = 1.5
_SCORE_CONTRIBS_WEIGHT  = 3.0


# ---------------------------------------------------------------------------
# Enumerations  (stringly-typed params invite typos; enums fail loudly)
# ---------------------------------------------------------------------------
class ReportFormat(str, Enum):
    SUMMARY  = "summary"
    DETAIL   = "detail"
    NAME_ONLY = "name"


class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW     = "new"


# ---------------------------------------------------------------------------
# Data model  (frozen dataclass = cheap value object, hashable, repr for free)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class UserRecord:
    uid:         int
    name:        str
    email:       str
    days_active: float
    status:      UserStatus
    score:       float


# ---------------------------------------------------------------------------
# Cache  (module-level; swap for LRU / Redis in production)
# ---------------------------------------------------------------------------
_cache: dict[int, dict] = {}


# ---------------------------------------------------------------------------
# Fetch layer
# ---------------------------------------------------------------------------
def _fetch_raw(session: Session, uid: int) -> dict:
    """Return the raw API payload for *uid*, populating the module cache."""
    if uid in _cache:
        return _cache[uid]

    response = session.get(f"{_API_BASE}/users/{uid}", timeout=_TIMEOUT_SECONDS)
    response.raise_for_status()   # raises HTTPError on 4xx / 5xx — don't silently swallow
    data: dict = response.json()  # handles charset decoding; prefer over json.loads(resp.text)
    _cache[uid] = data
    return data


# ---------------------------------------------------------------------------
# Transformation layer
# ---------------------------------------------------------------------------
def _classify_status(days_active: float) -> UserStatus:
    if days_active > _VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    if days_active > _REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW


def _to_record(uid: int, raw: dict) -> UserRecord:
    days_active = (time.time() - raw["created_ts"]) / _SECONDS_PER_DAY
    score = (
        raw["points"]        * _SCORE_POINTS_WEIGHT +
        raw["contributions"] * _SCORE_CONTRIBS_WEIGHT
    )
    return UserRecord(
        uid         = uid,
        name        = f"{raw['first']} {raw['last']}",
        email       = raw["contact"]["email"],
        days_active = days_active,
        status      = _classify_status(days_active),
        score       = score,
    )


# ---------------------------------------------------------------------------
# Formatting layer
# ---------------------------------------------------------------------------
def _format_record(record: UserRecord, fmt: ReportFormat) -> str:
    if fmt == ReportFormat.SUMMARY:
        return f"{record.name} ({record.status.value}) - Score: {record.score:.0f}"
    if fmt == ReportFormat.DETAIL:
        return (
            f"{record.name} <{record.email}> | "
            f"Status: {record.status.value} | "
            f"Days: {record.days_active:.0f} | "
            f"Score: {record.score:.0f}"
        )
    return record.name


# ---------------------------------------------------------------------------
# Error handling  (← see contribution request below)
# ---------------------------------------------------------------------------
def _handle_fetch_error(uid: int, exc: Exception) -> str | None:
    # TODO: implement — see contribution request
    ...


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_user_report(
    user_ids: list[int],
    report_format: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """
    Fetch user data for each ID and return a formatted report.

    Failures are handled by ``_handle_fetch_error`` — their policy
    is intentionally decoupled from the fetch/format logic.
    """
    lines:  list[str] = []
    failed: list[int] = []

    with requests.Session() as session:        # reuses the TCP connection across all requests
        for uid in user_ids:
            try:
                raw    = _fetch_raw(session, uid)
                record = _to_record(uid, raw)
                lines.append(_format_record(record, report_format))
            except (requests.RequestException, KeyError, TypeError) as exc:
                placeholder = _handle_fetch_error(uid, exc)
                if placeholder is not None:
                    lines.append(placeholder)
                failed.append(uid)

    body = "\n".join(lines)
    if failed:
        body += f"\n\n⚠ Failed to load {len(failed)} user(s): {failed}"

    sep = "=" * 40
    return f"{sep}\nUSER REPORT\n{sep}\n{body}"

def _handle_fetch_error(uid: int, exc: Exception) -> str | None:
    # Implement this — 5-10 lines
    ...