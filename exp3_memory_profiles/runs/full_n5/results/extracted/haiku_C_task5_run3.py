"""User report generation with caching and error handling."""

import logging
import time
from dataclasses import dataclass
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

# Configuration constants
API_BASE_URL = "https://api.example.com"
REQUEST_TIMEOUT = 3
SECONDS_PER_DAY = 86400
VETERAN_THRESHOLD = 365
REGULAR_THRESHOLD = 30
POINTS_WEIGHT = 1.5
CONTRIBUTIONS_WEIGHT = 3
MAX_WORKERS = 5  # Parallel API calls


@dataclass
class UserMetrics:
    """Structured user data with validation."""
    name: str
    email: str
    status: str
    days_active: float
    score: float


def _get_status(days_active: float) -> str:
    """Determine user status from days active."""
    if days_active > VETERAN_THRESHOLD:
        return "veteran"
    elif days_active > REGULAR_THRESHOLD:
        return "regular"
    return "new"


def _calculate_score(points: float, contributions: float) -> float:
    """Calculate user score from metrics."""
    return points * POINTS_WEIGHT + contributions * CONTRIBUTIONS_WEIGHT


def _extract_user_metrics(data: dict, current_time: float) -> Optional[UserMetrics]:
    """
    Extract and validate user metrics from API response.
    
    Args:
        data: API response dict
        current_time: Unix timestamp for consistency
        
    Returns:
        UserMetrics if data is valid, None if data is malformed
    """
    try:
        name = f"{data.get('first', 'Unknown')} {data.get('last', 'Unknown')}".strip()
        email = data.get("contact", {}).get("email", "N/A")
        
        created_ts = data.get("created_ts")
        if created_ts is None:
            logger.warning("Missing created_ts in user data")
            return None
            
        days_active = (current_time - created_ts) / SECONDS_PER_DAY
        status = _get_status(days_active)
        score = _calculate_score(
            data.get("points", 0),
            data.get("contributions", 0)
        )
        
        return UserMetrics(
            name=name,
            email=email,
            status=status,
            days_active=days_active,
            score=score
        )
    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"Failed to extract user metrics: {e}")
        return None


def _format_user_line(metrics: UserMetrics, format_type: str) -> str:
    """
    Format user metrics into a report line.
    
    Args:
        metrics: User metrics to format
        format_type: "summary", "detail", or "minimal"
        
    Returns:
        Formatted string
        
    Raises:
        ValueError: If format_type is invalid
    """
    formatters = {
        "summary": lambda m: f"{m.name} ({m.status}) - Score: {m.score:.0f}",
        "detail": lambda m: (
            f"{m.name} <{m.email}> | Status: {m.status} | "
            f"Days: {m.days_active:.0f} | Score: {m.score:.0f}"
        ),
        "minimal": lambda m: m.name,
    }
    
    if format_type not in formatters:
        raise ValueError(f"Invalid format: {format_type}. Must be one of {list(formatters.keys())}")
    
    return formatters[format_type](metrics)


def _fetch_user_data(user_id: int | str) -> Optional[dict]:
    """
    Fetch user data from API.
    
    Args:
        user_id: User identifier
        
    Returns:
        Parsed JSON response, or None on failure
    """
    try:
        url = urljoin(API_BASE_URL, f"/users/{user_id}")
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch user {user_id}: {e}")
        return None
    except ValueError as e:
        logger.error(f"Invalid JSON response for user {user_id}: {e}")
        return None


def get_user_report(
    user_ids: list[int | str],
    format_type: str = "summary",
    use_parallel: bool = True
) -> str:
    """
    Generate a user report for the given user IDs.
    
    Args:
        user_ids: List of user IDs to fetch
        format_type: Output format ("summary", "detail", or "minimal")
        use_parallel: Whether to fetch users in parallel
        
    Returns:
        Formatted report string
        
    Raises:
        ValueError: If format_type is invalid
    """
    # Validate format early
    valid_formats = {"summary", "detail", "minimal"}
    if format_type not in valid_formats:
        raise ValueError(f"Invalid format: {format_type}. Must be one of {valid_formats}")
    
    current_time = time.time()
    user_data_list = []
    
    if use_parallel and len(user_ids) > 1:
        # Fetch users in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_uid = {
                executor.submit(_fetch_user_data, uid): uid
                for uid in user_ids
            }
            for future in as_completed(future_to_uid):
                data = future.result()
                if data is not None:
                    user_data_list.append(data)
    else:
        # Sequential fetch for single user or when parallel disabled
        for uid in user_ids:
            data = _fetch_user_data(uid)
            if data is not None:
                user_data_list.append(data)
    
    # Extract metrics and format report
    results = []
    for data in user_data_list:
        metrics = _extract_user_metrics(data, current_time)
        if metrics is not None:
            line = _format_user_line(metrics, format_type)
            results.append(line)
    
    # Build report
    header = f"\n{'USER REPORT'.center(40, '=')}\n"
    return header + "\n".join(results) if results else header + "(No valid users)"