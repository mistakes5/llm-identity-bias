import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

# ── Constants ──────────────────────────────────────────────────
SECONDS_PER_DAY = 86_400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3.0
API_BASE_URL = "https://api.example.com/users"
REQUEST_TIMEOUT = 3

# Module-level cache (private, typed)
_cache: dict[int, dict] = {}


# ── Data types ─────────────────────────────────────────────────
class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name"


@dataclass(frozen=True)
class UserRecord:
    name: str
    email: str
    days_active: float
    status: str
    score: float


# ── Private helpers ────────────────────────────────────────────
def _fetch_user(user_id: int) -> Optional[dict]:
    """Fetch user data from the API, returning None on any failure."""
    if user_id in _cache:
        return _cache[user_id]

    try:
        resp = requests.get(f"{API_BASE_URL}/{user_id}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data: dict = resp.json()
        _cache[user_id] = data
        return data
    except requests.RequestException as exc:
        print(f"[warn] Could not fetch user {user_id}: {exc}")
        return None


def _compute_status(days_active: float) -> str:
    if days_active > VETERAN_THRESHOLD_DAYS:
        return "veteran"
    if days_active > REGULAR_THRESHOLD_DAYS:
        return "regular"
    return "new"


def _build_record(data: dict) -> UserRecord:
    name = f"{data['first']} {data['last']}"
    email = data["contact"]["email"]
    days_active = (time.time() - data["created_ts"]) / SECONDS_PER_DAY
    score = data["points"] * POINTS_MULTIPLIER + data["contributions"] * CONTRIBUTIONS_MULTIPLIER
    return UserRecord(
        name=name,
        email=email,
        days_active=days_active,
        status=_compute_status(days_active),
        score=score,
    )


def _format_record(record: UserRecord, fmt: ReportFormat) -> str:
    if fmt is ReportFormat.DETAIL:
        return (
            f"{record.name} <{record.email}> | Status: {record.status} "
            f"| Days: {record.days_active:.0f} | Score: {record.score:.0f}"
        )
    if fmt is ReportFormat.SUMMARY:
        return f"{record.name} ({record.status}) - Score: {record.score:.0f}"
    return record.name  # NAME_ONLY


# ── Public API ─────────────────────────────────────────────────
def get_user_report(
    user_ids: list[int],
    fmt: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """
    Fetch and format a report for the given user IDs.

    Args:
        user_ids: IDs to include in the report.
        fmt:      Output format — SUMMARY (default), DETAIL, or NAME_ONLY.

    Returns:
        Formatted report string. Unreachable users are skipped with a warning.
    """
    lines = []
    for uid in user_ids:
        data = _fetch_user(uid)
        if data is None:
            continue
        try:
            record = _build_record(data)
        except KeyError as exc:
            print(f"[warn] Malformed data for user {uid}, missing field {exc}")
            continue
        lines.append(_format_record(record, fmt))

    header = f"{'=' * 40}\nUSER REPORT\n{'=' * 40}"
    return header + "\n" + "\n".join(lines)