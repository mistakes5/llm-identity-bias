import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

# ── Constants ────────────────────────────────────────────────────────────────
API_BASE_URL           = "https://api.example.com/users"
REQUEST_TIMEOUT        = 3          # seconds
SECONDS_PER_DAY        = 86_400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
POINTS_MULTIPLIER      = 1.5
CONTRIBUTIONS_MULTIPLIER = 3.0

# Module-level cache (private by convention)
_cache: dict[int, dict] = {}


# ── Domain types ──────────────────────────────────────────────────────────────
class ReportFormat(str, Enum):
    SUMMARY  = "summary"
    DETAIL   = "detail"
    NAME_ONLY = "name"


class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW     = "new"


@dataclass(frozen=True)
class UserRecord:
    name:        str
    email:       str
    days_active: float
    status:      UserStatus
    score:       float


# ── Helpers ───────────────────────────────────────────────────────────────────
def fetch_user(uid: int) -> Optional[dict]:
    """Return raw user data from cache or API; None on any failure."""
    if uid in _cache:
        return _cache[uid]

    try:
        resp = requests.get(f"{API_BASE_URL}/{uid}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()          # surfaces 4xx/5xx as exceptions
        data: dict = resp.json()         # handles encoding; no manual json.loads
        _cache[uid] = data
        return data
    except requests.RequestException as exc:
        # Replace with logging.warning(…) in production
        print(f"[warn] Could not fetch user {uid}: {exc}")
        return None


def _compute_status(days_active: float) -> UserStatus:
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    if days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW


def parse_user(data: dict) -> UserRecord:
    """Map raw API payload to a typed, immutable UserRecord."""
    name        = f"{data['first']} {data['last']}"
    email       = data["contact"]["email"]
    days_active = (time.time() - data["created_ts"]) / SECONDS_PER_DAY
    score       = (data["points"] * POINTS_MULTIPLIER
                   + data["contributions"] * CONTRIBUTIONS_MULTIPLIER)

    return UserRecord(
        name=name,
        email=email,
        days_active=days_active,
        status=_compute_status(days_active),
        score=score,
    )


def format_user(record: UserRecord, report_format: ReportFormat) -> str:
    """Render a single UserRecord line according to the requested format."""
    match report_format:
        case ReportFormat.SUMMARY:
            return f"{record.name} ({record.status.value}) - Score: {record.score:.0f}"
        case ReportFormat.DETAIL:
            return (
                f"{record.name} <{record.email}> | "
                f"Status: {record.status.value} | "
                f"Days: {record.days_active:.0f} | "
                f"Score: {record.score:.0f}"
            )
        case _:
            return record.name


# ── Public API ────────────────────────────────────────────────────────────────
def get_user_report(
    user_ids: list[int],
    report_format: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """
    Fetch and format a report for the given user IDs.

    Args:
        user_ids:      IDs to include; failures are silently skipped.
        report_format: Controls line verbosity (SUMMARY | DETAIL | NAME_ONLY).

    Returns:
        A formatted, header-wrapped report string.
    """
    lines: list[str] = []

    for uid in user_ids:
        data = fetch_user(uid)
        if data is None:
            continue                     # already logged inside fetch_user
        lines.append(format_user(parse_user(data), report_format))

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(lines)