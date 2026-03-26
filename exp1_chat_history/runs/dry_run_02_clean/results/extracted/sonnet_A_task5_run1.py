import time
from dataclasses import dataclass
from enum import Enum

import requests

# --- Constants -----------------------------------------------------------

API_BASE_URL = "https://api.example.com/users"
REQUEST_TIMEOUT = 3
DAYS_TO_SECONDS = 86_400

VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
POINTS_MULTIPLIER = 1.5
CONTRIBUTIONS_MULTIPLIER = 3.0

# Module-level cache (private by convention)
_cache: dict[int, dict] = {}


# --- Data model ----------------------------------------------------------

class ReportFormat(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    NAME_ONLY = "name"


@dataclass(frozen=True)
class UserRecord:
    name: str
    email: str
    days_active: float
    score: float

    @property
    def status(self) -> str:
        if self.days_active > VETERAN_THRESHOLD_DAYS:
            return "veteran"
        if self.days_active > REGULAR_THRESHOLD_DAYS:
            return "regular"
        return "new"

    def format_line(self, fmt: ReportFormat) -> str:
        if fmt == ReportFormat.SUMMARY:
            return f"{self.name} ({self.status}) - Score: {self.score:.0f}"
        if fmt == ReportFormat.DETAIL:
            return (
                f"{self.name} <{self.email}> | Status: {self.status} "
                f"| Days: {self.days_active:.0f} | Score: {self.score:.0f}"
            )
        return self.name


# --- Helpers -------------------------------------------------------------

def _fetch_user(uid: int) -> dict | None:
    """Return cached or freshly fetched user data, or None on failure."""
    if uid in _cache:
        return _cache[uid]
    try:
        resp = requests.get(f"{API_BASE_URL}/{uid}", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data: dict = resp.json()
        _cache[uid] = data
        return data
    except requests.RequestException as exc:
        print(f"Warning: could not fetch user {uid}: {exc}")
        return None


def _parse_record(data: dict) -> UserRecord:
    name = f"{data['first']} {data['last']}"
    email = data["contact"]["email"]
    days_active = (time.time() - data["created_ts"]) / DAYS_TO_SECONDS
    score = (
        data["points"] * POINTS_MULTIPLIER
        + data["contributions"] * CONTRIBUTIONS_MULTIPLIER
    )
    return UserRecord(name=name, email=email, days_active=days_active, score=score)


# --- Public API ----------------------------------------------------------

def get_user_report(
    user_ids: list[int],
    fmt: ReportFormat = ReportFormat.SUMMARY,
) -> str:
    """
    Fetch user data for each ID and return a formatted report string.

    Args:
        user_ids: Ordered list of user IDs to include.
        fmt:      Output verbosity — SUMMARY, DETAIL, or NAME_ONLY.

    Returns:
        A report string with a header followed by one line per resolved user.
        Users that cannot be fetched are silently skipped after logging a warning.
    """
    lines: list[str] = []
    for uid in user_ids:
        data = _fetch_user(uid)
        if data is None:
            continue
        record = _parse_record(data)
        lines.append(record.format_line(fmt))

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(lines)