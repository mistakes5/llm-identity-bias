import time
from dataclasses import dataclass
from enum import Enum
from typing import Literal

import requests

# ── Constants ────────────────────────────────────────────────────────────────

API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3  # seconds

SECONDS_PER_DAY = 86_400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30

POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3.0

# ── Types ────────────────────────────────────────────────────────────────────

ReportFormat = Literal["summary", "detail", "name"]


class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"


@dataclass(frozen=True)
class UserRecord:
    name: str
    email: str
    days_active: float
    status: UserStatus
    score: float


# ── Cache ─────────────────────────────────────────────────────────────────────

_cache: dict[int, dict] = {}


# ── Private helpers ───────────────────────────────────────────────────────────

def _fetch_user(user_id: int) -> dict | None:
    """Fetch raw user data from the API. Returns None on any network failure."""
    if user_id in _cache:
        return _cache[user_id]

    try:
        resp = requests.get(
            f"{API_BASE_URL}/users/{user_id}",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"[warn] Could not fetch user {user_id}: {exc}")
        return None

    _cache[user_id] = data
    return data


def _classify_status(days_active: float) -> UserStatus:
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    if days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW


def _parse_user(data: dict) -> UserRecord:
    """Map raw API payload to a typed UserRecord. Raises KeyError on missing fields."""
    days_active = (time.time() - data["created_ts"]) / SECONDS_PER_DAY
    return UserRecord(
        name=f"{data['first']} {data['last']}",
        email=data["contact"]["email"],
        days_active=days_active,
        status=_classify_status(days_active),
        score=data["points"] * POINTS_MULTIPLIER + data["contributions"] * CONTRIBUTIONS_MULTIPLIER,
    )


def _format_record(record: UserRecord, fmt: ReportFormat) -> str:
    if fmt == "detail":
        return (
            f"{record.name} <{record.email}> | "
            f"Status: {record.status.value} | "
            f"Days: {record.days_active:.0f} | "
            f"Score: {record.score:.0f}"
        )
    if fmt == "summary":
        return f"{record.name} ({record.status.value}) - Score: {record.score:.0f}"
    return record.name  # "name" or unrecognised format


# ── Public API ────────────────────────────────────────────────────────────────

def get_user_report(
    user_ids: list[int],
    fmt: ReportFormat = "summary",
) -> str:
    """
    Fetch and format a report for the given user IDs.

    Args:
        user_ids: User IDs to include.
        fmt: Output format — "summary", "detail", or "name".

    Returns:
        A formatted report string. Unreachable or malformed users are skipped
        with a warning rather than aborting the entire report.
    """
    lines: list[str] = []

    for uid in user_ids:
        data = _fetch_user(uid)
        if data is None:
            continue
        try:
            record = _parse_user(data)
        except KeyError as exc:
            print(f"[warn] Malformed data for user {uid} — missing field {exc}")
            continue
        lines.append(_format_record(record, fmt))

    sep = "=" * 40
    return f"{sep}\nUSER REPORT\n{sep}\n" + "\n".join(lines)