"""User report generation with API fetching and in-memory caching."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import requests

# Module-level cache keyed by user ID.
# Not thread-safe — wrap with threading.Lock or switch to
# cachetools.TTLCache for concurrent/long-running processes.
_user_cache: dict[int, dict] = {}

FormatStyle = Literal["summary", "detail", "name"]


@dataclass(frozen=True)
class UserRecord:
    """Parsed, domain-level representation of a single user."""
    name: str
    email: str
    days_active: float
    score: float
    status: str


# ── Fetching ────────────────────────────────────────────────────────────────

def _fetch_user(user_id: int) -> dict | None:
    """Return raw API data for *user_id*, hitting the cache first."""
    if user_id in _user_cache:
        return _user_cache[user_id]

    try:
        resp = requests.get(
            f"https://api.example.com/users/{user_id}",
            timeout=3,
        )
        resp.raise_for_status()   # raises HTTPError on 4xx / 5xx
        data: dict = resp.json()
    except requests.RequestException as exc:
        print(f"[warn] Failed to fetch user {user_id}: {exc}")
        return None

    _user_cache[user_id] = data
    return data


# ── Parsing ─────────────────────────────────────────────────────────────────

def _classify_status(days_active: float) -> str:
    if days_active > 365:
        return "veteran"
    if days_active > 30:
        return "regular"
    return "new"


def _parse_user(raw: dict) -> UserRecord:
    name = f"{raw['first']} {raw['last']}"
    email = raw["contact"]["email"]
    days_active = (time.time() - raw["created_ts"]) / 86400
    score = raw["points"] * 1.5 + raw["contributions"] * 3.0
    return UserRecord(
        name=name,
        email=email,
        days_active=days_active,
        score=score,
        status=_classify_status(days_active),
    )


# ── Formatting ───────────────────────────────────────────────────────────────

def _format_line(record: UserRecord, style: FormatStyle) -> str:
    match style:
        case "summary":
            return f"{record.name} ({record.status}) - Score: {record.score:.0f}"
        case "detail":
            return (
                f"{record.name} <{record.email}> | Status: {record.status}"
                f" | Days: {record.days_active:.0f} | Score: {record.score:.0f}"
            )
        case _:
            return record.name


# ── Public API ───────────────────────────────────────────────────────────────

def get_user_report(
    user_ids: list[int],
    *,                          # keyword-only — prevents positional misuse
    style: FormatStyle = "summary",
) -> str:
    """Fetch users and return a formatted multi-line report.

    Args:
        user_ids: IDs to include in the report.
        style: "summary" (default), "detail", or "name".

    Returns:
        A string with a header followed by one line per successfully
        fetched user. Users that fail to fetch or parse are skipped.
    """
    lines: list[str] = []

    for uid in user_ids:
        raw = _fetch_user(uid)
        if raw is None:
            continue  # fetch error already logged in _fetch_user

        try:
            record = _parse_user(raw)
        except KeyError as exc:
            print(f"[warn] Missing field {exc} in data for user {uid} — skipping.")
            continue

        lines.append(_format_line(record, style))

    sep = "=" * 40
    return f"{sep}\nUSER REPORT\n{sep}\n" + "\n".join(lines)

from collections.abc import Callable

def get_user_report(
    user_ids: list[int],
    *,
    style: FormatStyle = "summary",
    on_error: Callable[[int, Exception | None], None] | None = None,  # ← your design
) -> str:
    ...
    for uid in user_ids:
        raw = _fetch_user(uid)
        if raw is None:
            # TODO: call on_error here? raise? collect? your call.
            continue