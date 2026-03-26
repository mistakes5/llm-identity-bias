import requests
import time

# --- Constants: named values instead of scattered "magic numbers" ---
# If these need to change, you update them in one place only
SCORE_POINTS_MULTIPLIER = 1.5
SCORE_CONTRIBUTIONS_MULTIPLIER = 3
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD_DAYS = 365
REGULAR_THRESHOLD_DAYS = 30
API_BASE_URL = "https://api.example.com/users/"
REQUEST_TIMEOUT_SECONDS = 3

# The cache lives here, at module level, with a private name (_prefix)
# to signal it's an internal detail — not meant to be used directly
_user_cache = {}


def fetch_user(uid):
    """
    Fetches one user from the API (or returns cached data if already loaded).
    Returns the user data dict, or None if something went wrong.
    """
    # Return immediately if we've already loaded this user
    if uid in _user_cache:
        return _user_cache[uid]

    url = API_BASE_URL + str(uid)  # Build the full URL

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()  # Raises an error for bad status codes (4xx, 5xx)
        data = resp.json()       # .json() handles parsing — no need for json.loads()
        _user_cache[uid] = data  # Save to cache so we don't fetch again
        return data

    except requests.RequestException as error:
        # Only catch network/HTTP errors — not unrelated bugs like typos or crashes
        print(f"Warning: Could not fetch user {uid}: {error}")
        return None  # Signal that this user should be skipped


def calculate_days_active(created_ts):
    """Returns how many days ago the account was created."""
    return (time.time() - created_ts) / SECONDS_PER_DAY


def calculate_score(points, contributions):
    """Calculates a user's engagement score from their points and contributions."""
    return (points * SCORE_POINTS_MULTIPLIER) + (contributions * SCORE_CONTRIBUTIONS_MULTIPLIER)


def format_user_line(name, email, status, days_active, score, report_format):
    """
    Formats one user's info into a display string.
    report_format can be "summary", "detail", or anything else (name only).
    """
    if report_format == "summary":
        return f"{name} ({status}) - Score: {score:.0f}"
    elif report_format == "detail":
        return f"{name} <{email}> | Status: {status} | Days: {days_active:.0f} | Score: {score:.0f}"
    else:
        return name  # Fallback: just the name


def get_user_report(user_ids, report_format="summary"):
    """
    Fetches user data for each ID and returns a formatted report string.

    Parameters:
        user_ids      - list of user IDs to include
        report_format - "summary", "detail", or anything else for name-only
    """
    # ✓ No mutable default argument here — 'lines' is created fresh every call
    lines = []

    for uid in user_ids:
        data = fetch_user(uid)

        if data is None:
            continue  # Skip users we couldn't load (error was already printed)

        name = data["first"] + " " + data["last"]
        email = data["contact"]["email"]
        days_active = calculate_days_active(data["created_ts"])
        status = calculate_status(days_active)  # ← you'll write this below!
        score = calculate_score(data["points"], data["contributions"])

        line = format_user_line(name, email, status, days_active, score, report_format)
        lines.append(line)

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    return header + "\n" + "\n".join(lines)

def calculate_status(days_active):
    """
    Returns a status label ("veteran", "regular", or "new")
    based on how many days the user has been active.
    """
    # TODO: Your code here!
    # Hint: you have VETERAN_THRESHOLD_DAYS and REGULAR_THRESHOLD_DAYS available
    # Think about: should you check the bigger threshold first, or the smaller one?
    pass