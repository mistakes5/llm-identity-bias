"""Shared utilities for the profile-bias experiment.

Provides an API client that calls ``claude --bare --print`` directly via
subprocess, bypassing the Claude Code agent system prompt.  This gives raw
model completions without tool-use, CLAUDE.md injection, or permission
prompts — exactly what the experiment needs.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ERROR_MARKERS: list[str] = [
    "rate limit exceeded",
    "rate limit reached",
    "api rate limit",
    "quota exceeded",
    "quota exhausted",
    "too many requests",
    "unauthorized",
    "forbidden",
    "connection error",
    "connection timed out",
    "request timeout",
    "internal server error",
    "503 service unavailable",
    "502 bad gateway",
    "http 429",
]

# Sonnet pricing as rough upper-bound estimate ($ per million tokens).
_INPUT_COST_PER_MTOK: float = 3.0
_OUTPUT_COST_PER_MTOK: float = 15.0


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Thread-safe circuit breaker for external API calls.

    After *failure_threshold* consecutive failures the breaker *trips* and
    remains open for *cooldown_seconds*.  While open, ``is_open`` returns
    ``True`` so callers can back off without hitting the API.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 120.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._consecutive_failures: int = 0
        self._tripped_at: float | None = None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        """Return ``True`` when the breaker is tripped and cooldown has not elapsed."""
        with self._lock:
            if self._tripped_at is None:
                return False
            elapsed = time.monotonic() - self._tripped_at
            if elapsed >= self._cooldown_seconds:
                # Cooldown expired — reset the breaker.
                self._tripped_at = None
                self._consecutive_failures = 0
                return False
            return True

    def record_success(self) -> None:
        """Reset failure counter on a successful call."""
        with self._lock:
            self._consecutive_failures = 0
            self._tripped_at = None

    def record_failure(self) -> None:
        """Increment failure counter; trip the breaker if threshold is reached."""
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failure_threshold:
                self._tripped_at = time.monotonic()


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------


def validate_response(text: str | None) -> bool:
    """Return ``True`` if *text* looks like valid model content.

    Returns ``False`` when the text is empty or suspiciously short.
    Error-marker checks only apply to short responses (<500 chars) to avoid
    false positives on long responses that happen to mention error concepts.
    """
    if not text or len(text) < 10:
        return False
    # Only check error markers on short responses — long responses with code
    # are real content even if they mention "rate limit" or "timeout" concepts.
    if len(text) < 500:
        lower = text.lower()
        if any(marker in lower for marker in _ERROR_MARKERS):
            return False
    return True


# ---------------------------------------------------------------------------
# Anthropic client wrapper
# ---------------------------------------------------------------------------


class AnthropicCallError(Exception):
    """Raised when an API call fails after exhausting retries or validation."""


# ---------------------------------------------------------------------------
# Model name mapping for the CLI
# ---------------------------------------------------------------------------

_CLI_MODEL_MAP: dict[str, str] = {
    "claude-sonnet-4": "sonnet",
    "claude-haiku-4": "haiku",
    "claude-opus-4": "opus",
    "sonnet": "sonnet",
    "haiku": "haiku",
    "opus": "opus",
}


def _build_prompt(messages: list[dict[str, str]]) -> str:
    """Flatten a message array into a single prompt string for the CLI.

    Each message is wrapped in XML-style role tags so the model can
    distinguish prior conversation turns from the final request.
    """
    parts: list[str] = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            parts.append(f"<human>\n{content}\n</human>")
        elif role == "assistant":
            parts.append(f"<assistant>\n{content}\n</assistant>")
    return "\n\n".join(parts)


class AnthropicClient:
    """Calls ``claude --bare --print`` via subprocess for raw completions.

    Uses ``--bare`` to strip the Claude Code agent system prompt, tools,
    CLAUDE.md, hooks, and all other agent behavior.  The model responds
    as a plain completer — no permission prompts, no file-writing proposals.

    Token counts are estimated from character counts since the CLI doesn't
    report accurate token usage.
    """

    def __init__(
        self,
        default_temperature: float = 0.3,
        default_max_tokens: int = 4096,
        inter_call_delay: float = 0.5,
    ) -> None:
        self.breaker = CircuitBreaker()
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        self.inter_call_delay = inter_call_delay
        self.call_count: int = 0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self._logger = logging.getLogger("experiment.api")

    def send(
        self,
        model: str,
        messages: list[dict[str, str]],
        system: str | None = None,
        profile_only: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        skip_validation: bool = False,
    ) -> dict[str, Any]:
        """Send *messages* via ``claude --print`` and return a result dict.

        Parameters
        ----------
        system:
            System prompt text. When *profile_only* is ``True``, this is the
            ONLY system content (no developer instructions added). When
            ``None`` and *profile_only* is ``False``, a default developer
            instruction is used.
        profile_only:
            If ``True``, the system prompt is passed as-is with no default
            instructions. If *system* is ``None``, no ``--system-prompt``
            flag is passed at all (Profile B / control condition).

        Returns
        -------
        dict
            ``{"text": str, "stop_reason": str, "input_tokens": int,
            "output_tokens": int, "model": str, "system_chars": int,
            "prompt_chars": int}``
        """
        max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        if self.breaker.is_open:
            self._logger.warning("Circuit breaker open — waiting for cooldown.")
            time.sleep(self.breaker._cooldown_seconds)
            if self.breaker.is_open:
                raise AnthropicCallError("Circuit breaker still open after cooldown.")

        cli_model = _CLI_MODEL_MAP.get(model, model)
        prompt = _build_prompt(messages)
        prompt_chars = len(prompt)

        # System prompt logic:
        # - profile_only=True + system provided → use ONLY that text
        # - profile_only=True + system=None → no --system-prompt (control)
        # - profile_only=False → default developer instructions
        if profile_only:
            effective_system = system  # None means omit entirely
        else:
            effective_system = system or (
                "You are a Python developer. When asked to write code, respond "
                "with the code in a markdown python code block. Do not ask for "
                "permissions. Do not propose file operations. Do not mention "
                "tools or file paths. Just write the code directly."
            )

        system_chars = len(effective_system) if effective_system else 0

        cmd = [
            "claude",
            "--print",
            "--model", cli_model,
            "--output-format", "text",
            "--no-session-persistence",
        ]
        # Pass --system-prompt for any non-None value (including empty string)
        # to replace the default CLI agent prompt across all conditions.
        if effective_system is not None:
            cmd.extend(["--system-prompt", effective_system])
        cmd.append(prompt)

        # Retry loop
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                start = time.monotonic()
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=300,
                )
                elapsed_ms = (time.monotonic() - start) * 1000

                if result.returncode != 0:
                    err_msg = result.stderr.strip() or f"exit code {result.returncode}"
                    self._logger.warning(
                        "CLI error (attempt %d/%d): %s", attempt, max_retries, err_msg,
                    )
                    if attempt >= max_retries:
                        self.breaker.record_failure()
                        raise AnthropicCallError(f"CLI failed after {max_retries} attempts: {err_msg}")
                    time.sleep(2 * attempt)
                    continue

                text = result.stdout.strip()

                if not skip_validation and not validate_response(text):
                    self.breaker.record_failure()
                    raise AnthropicCallError(
                        f"Response failed validation (len={len(text)}): {text[:120]}..."
                    )

                est_input_tokens = (prompt_chars + system_chars) // 4
                est_output_tokens = len(text) // 4

                self.breaker.record_success()
                self.call_count += 1
                self.total_input_tokens += est_input_tokens
                self.total_output_tokens += est_output_tokens

                self._logger.debug(
                    "CLI call #%d — model=%s  sys=%d chars  prompt=%d chars  ~%d in  ~%d out  %.0fms",
                    self.call_count, cli_model,
                    system_chars, prompt_chars,
                    est_input_tokens, est_output_tokens, elapsed_ms,
                )

                time.sleep(self.inter_call_delay)

                return {
                    "text": text,
                    "stop_reason": "end_turn",
                    "input_tokens": est_input_tokens,
                    "output_tokens": est_output_tokens,
                    "model": cli_model,
                    "system_chars": system_chars,
                    "prompt_chars": prompt_chars,
                }

            except subprocess.TimeoutExpired:
                self._logger.warning("CLI timed out (attempt %d/%d)", attempt, max_retries)
                if attempt >= max_retries:
                    self.breaker.record_failure()
                    raise AnthropicCallError("CLI timed out after 300s")
                time.sleep(2 * attempt)

            except AnthropicCallError:
                raise

            except Exception as exc:
                self.breaker.record_failure()
                raise AnthropicCallError(f"Unexpected error: {exc}") from exc

        raise AnthropicCallError("Exhausted retries")

    def send_for_profile(
        self,
        model: str,
        profile_text: str | None,
        coding_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Send a coding prompt with profile text as the sole system prompt.

        For the memory-injection experiment: *profile_text* becomes the
        ``--system-prompt`` and the coding prompt is the only user message.
        Pass ``None`` for Profile B (control / no profile).
        """
        messages = [{"role": "user", "content": coding_prompt}]
        return self.send(
            model=model, messages=messages,
            system=profile_text, profile_only=True,
            temperature=temperature, max_tokens=max_tokens,
        )

    def get_usage_summary(self) -> dict[str, Any]:
        """Return cumulative usage stats (token counts are estimates)."""
        input_cost = (self.total_input_tokens / 1_000_000) * _INPUT_COST_PER_MTOK
        output_cost = (self.total_output_tokens / 1_000_000) * _OUTPUT_COST_PER_MTOK
        return {
            "call_count": self.call_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": round(input_cost + output_cost, 4),
        }


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def setup_logging(output_dir: str | Path, name: str = "experiment") -> logging.Logger:
    """Configure dual logging to console (INFO) and file (DEBUG).

    The log file is written to ``<output_dir>/<name>.log``.

    Returns
    -------
    logging.Logger
        The configured logger instance.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if called more than once.
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler — INFO and above.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler — DEBUG and above.
    file_handler = logging.FileHandler(output_dir / f"{name}.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------


def save_json(data: Any, path: str | Path) -> None:
    """Write *data* as pretty-printed JSON, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)


def load_json(path: str | Path) -> Any:
    """Load and return a JSON file."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------


def ensure_dirs(*paths: str | Path) -> None:
    """Create each directory in *paths* (with parents) if it does not exist."""
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)
