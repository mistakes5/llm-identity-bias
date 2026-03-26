import requests
import time

# ── Constants ────────────────────────────────────────────────────────────────
# Giving magic numbers names makes code readable and easy to update later.

API_BASE_URL       = "https://api.example.com/users/"
REQUEST_TIMEOUT    = 3        # seconds before we give up waiting for the server

SECONDS_IN_A_DAY   = 86400   # 60 seconds * 60 minutes * 24 hours

VETERAN_DAYS       = 365     # accounts older than this → "veteran"
REGULAR_DAYS       = 30      # accounts older than this → "regular"

POINTS_MULTIPLIER  = 1.5
CONTRIB_MULTIPLIER = 3.0

MAX_CACHE_SIZE     = 1000    # cap prevents unbounded memory growth

# ── Module-level cache ───────────────────────────────────────────────────────
_user_cache = {}


def fetch_user(user_id):
    """Returns a user data dict, or None if anything went wrong."""
    if user_id in _user_cache:
        return _user_cache[user_id]

    try:
        url = f"{API_BASE_URL}{user_id}"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)

        # raise_for_status() turns a 404 or 500 response into an actual error.
        # Without this, a "Not Found" page looks like a success!
        resp.raise_for_status()

        data = resp.json()   # cleaner than json.loads(resp.text)

        if len(_user_cache) < MAX_CACHE_SIZE:
            _user_cache[user_id] = data

        return data

    except requests.exceptions.Timeout:
        print(f"Warning: request timed out for user {user_id}")
        return None

    except requests.exceptions.HTTPError as err:
        # Server replied but with an error code (404, 500, etc.)
        print(f"Warning: HTTP error for user {user_id}: {err}")
        return None

    except requests.exceptions.RequestException as err:
        # Catch-all for other network problems (no internet, DNS failure, etc.)
        print(f"Warning: network error for user {user_id}: {err}")
        return None


def determine_status(days_active):
    """
    Returns "veteran", "regular", or "new" based on how long the account has been active.

    TODO: Your code goes here! See the note at the bottom.
    """
    pass   # ← replace this


def calculate_score(points, contributions):
    """Returns a single number representing a user's activity score."""
    return points * POINTS_MULTIPLIER + contributions * CONTRIB_MULTIPLIER


def format_user_line(data, report_format):
    """Turns a user data dict into one formatted string, or None if name is missing."""
    # .get() returns a default value instead of crashing with KeyError
    first = data.get("first", "")
    last  = data.get("last", "")
    name  = f"{first} {last}".strip()   # .strip() removes stray spaces

    if not name:
        return None

    contact = data.get("contact", {})   # {} = empty dict if "contact" is missing
    email   = contact.get("email", "no email")

    created_ts  = data.get("created_ts", time.time())
    days_active = (time.time() - created_ts) / SECONDS_IN_A_DAY
    status      = determine_status(days_active)

    score = calculate_score(
        points        = data.get("points", 0),
        contributions = data.get("contributions", 0),
    )

    if report_format == "summary":
        return f"{name} ({status}) - Score: {score:.0f}"
    elif report_format == "detail":
        return f"{name} <{email}> | Status: {status} | Days: {days_active:.0f} | Score: {score:.0f}"
    else:
        return name   # name-only fallback


def get_user_report(user_ids, report_format="summary"):
    """Fetches data for each user ID and returns a formatted report string."""
    lines = []   # fresh list every call — no mutable default!

    for uid in user_ids:
        data = fetch_user(uid)

        if data is None:
            continue   # fetch failed; warning already printed inside fetch_user()

        line = format_user_line(data, report_format)

        if line is not None:
            lines.append(line)

    header = "=" * 40 + "\nUSER REPORT\n" + "=" * 40
    body   = "\n".join(lines) if lines else "(no users to display)"
    return f"{header}\n{body}"

def determine_status(days_active):
    # Your code here — should be about 5 lines using if/elif/else
    pass