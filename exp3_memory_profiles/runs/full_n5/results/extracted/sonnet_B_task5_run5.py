"""User report generation — fetch, parse, and format user records from the API."""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants  (no more magic numbers scattered through logic)
# ---------------------------------------------------------------------------

SECONDS_PER_DAY = 86_400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
POINTS_WEIGHT = 1.5
CONTRIBUTIONS_WEIGHT = 3.0
REQUEST_TIMEOUT_S = 3
API_BASE_URL = "https://api.example.com"

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name"

class UserStatus(str, Enum):
    VETERAN = "veteran"
    REGULAR = "regular"
    NEW = "new"

@dataclass(frozen=True)
class UserRecord:
    user_id: int
    name: str
    email: str
    days_active: float
    status: UserStatus
    score: float

# ---------------------------------------------------------------------------
# Cache  (private, module-level — no mutable default arguments)
# ---------------------------------------------------------------------------

_user_cache: dict[int, dict] = {}

# ---------------------------------------------------------------------------
# Layer 1 — Fetch
# ---------------------------------------------------------------------------

def fetch_user(user_id: int) -> Optional[dict]:
    """Return raw user data from the API, using an in-memory cache.
    Returns None and logs a warning on any network or HTTP error.
    """
    if user_id in _user_cache:
        return _user_cache[user_id]

    try:
        resp = requests.get(
            f"{API_BASE_URL}/users/{user_id}",
            timeout=REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()       # surfaces 4xx/5xx as an exception
        data: dict = resp.json()      # no manual json.loads(resp.text) needed
    except requests.RequestException as exc:
        logger.warning("Failed to fetch user %s: %s", user_id, exc)
        return None

    _user_cache[user_id] = data
    return data

# ---------------------------------------------------------------------------
# Layer 2 — Parse
# ---------------------------------------------------------------------------

def _classify_status(days_active: float) -> UserStatus:
    if days_active > VETERAN_THRESHOLD_DAYS:
        return UserStatus.VETERAN
    if days_active > REGULAR_THRESHOLD_DAYS:
        return UserStatus.REGULAR
    return UserStatus.NEW

def parse_user(user_id: int, raw: dict) -> Optional[UserRecord]:
    """Parse raw API data into a validated, immutable UserRecord.
    Returns None and logs a warning if required fields are missing.
    """
    try:
        name = f"{raw['first']} {raw['last']}"
        email = raw["contact"]["email"]
        days_active = (time.time() - raw["created_ts"]) / SECONDS_PER_DAY
    except (KeyError, TypeError) as exc:
        logger.warning("Malformed data for user %s: %s", user_id, exc)
        return None

    score = (
        raw.get("points", 0) * POINTS_WEIGHT
        + raw.get("contributions", 0) * CONTRIBUTIONS_WEIGHT
    )
    return UserRecord(
        user_id=user_id,
        name=name,
        email=email,
        days_active=days_active,
        status=_classify_status(days_active),
        score=score,
    )

# ---------------------------------------------------------------------------
# Layer 3 — Format
# ---------------------------------------------------------------------------

def format_line(record: UserRecord, report_format: ReportFormat) -> str:
    """Render one UserRecord as a single report line."""
    if report_format == ReportFormat.DETAIL:
        return (
            f"{record.name} <{record.email}> | "
            f"Status: {record.status.value} | "
            f"Days: {record.days_active:.0f} | "
            f"Score: {record.score:.0f}"
        )
    if report_format == ReportFormat.SUMMARY:
        return f"{record.name} ({record.status.value}) - Score: {record.score:.0f}"
    return record.name

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _handle_failed_user(user_id: int) -> Optional[str]:
    """Return a report line for a user that could not be fetched or parsed.

    TODO — implement your preferred error-surface strategy here (5–10 lines).
    """
    return None  # placeholder — see contribution request below

def get_user_report(
    user_ids: list[int],
    report_format: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """Fetch and format a report for the given user IDs."""
    lines: list[str] = []

    for uid in user_ids:
        raw = fetch_user(uid)
        if raw is None:
            if (line := _handle_failed_user(uid)):
                lines.append(line)
            continue

        record = parse_user(uid, raw)
        if record is None:
            if (line := _handle_failed_user(uid)):
                lines.append(line)
            continue

        lines.append(format_line(record, report_format))

    separator = "=" * 40
    return f"{separator}\nUSER REPORT\n{separator}\n" + "\n".join(lines)

def _handle_failed_user(user_id: int) -> Optional[str]:
    # Option A — silent skip (current placeholder)
    return None

    # Option B — visible placeholder in the report
    return f"[User {user_id}: data unavailable]"

    # Option C — raise immediately to abort the whole report
    raise RuntimeError(f"Could not load user {user_id}; aborting report")

    # Option D — collect failures separately (requires a module-level list
    #             or a result-wrapper type instead of a plain str return)