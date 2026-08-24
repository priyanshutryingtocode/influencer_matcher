"""Gemini API client factory (used for ranking; embeddings are local)."""

import logging
import re
import time

from google import genai
from google.genai import errors, types

from . import config

logger = logging.getLogger(__name__)

# Free-tier (and many paid-tier) quotas throttle generate_content bursts. On
# a 429 the API tells us exactly how long to wait; honor that backoff and
# retry instead of immediately treating the throttle as an outage.
_RETRY_MESSAGE_MS = re.compile(r"Please retry in ([\d.]+)s", re.IGNORECASE)


def get_client() -> genai.Client:
    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Create a .env file and add your key, "
            "or export GEMINI_API_KEY directly. Get a key at "
            "https://aistudio.google.com/apikey"
        )
    return genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=config.GEMINI_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=config.GEMINI_RETRY_ATTEMPTS),
        ),
    )


def _throttle_sleep_seconds(error: Exception) -> float:
    """Return how long the server asked us to wait before retrying a 429.

    The structured RetryInfo carries a delay when available; otherwise we
    parse the human-readable 'Please retry in Xs' from the message. Falls
    back to a modest floor so we never retry instantly."""
    info = getattr(error, "details", None) or getattr(error, "error", None)
    retry = getattr(info, "retry_info", None)
    delay = getattr(retry, "retry_delay", None)
    seconds = getattr(delay, "seconds", None)
    if isinstance(seconds, (int, float)) and seconds > 0:
        return float(seconds)

    message = f"{getattr(error, 'message', '')} {str(error)}"
    match = _RETRY_MESSAGE_MS.search(message or "")
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 1.0


def generate_content_throttled(
    client,
    model: str,
    contents,
    gen_config: types.GenerateContentConfig | None = None,
    attempts: int | None = None,
):
    """Call generate_content, honoring 429 rate-limit backoffs with retries.

    A 429 (RESOURCE_EXHAUSTED) is a quota throttle, not an outage: sleep the
    server-provided delay, then retry, up to `attempts` (defaults to
    GEMINI_RETRY_ATTEMPTS). Any other error is re-raised unchanged so callers
    keep their existing error handling and fallbacks.
    """
    attempts = config.GEMINI_RETRY_ATTEMPTS if attempts is None else attempts
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return client.models.generate_content(model=model, contents=contents, config=gen_config)
        except errors.ClientError as e:
            ctx = f"{getattr(e, 'code', '')} {getattr(e, 'message', '')} {str(e)}"
            is_throttle = "429" in ctx and "RESOURCE_EXHAUSTED" in ctx
            if not is_throttle or attempt == attempts - 1:
                raise
            backoff = _throttle_sleep_seconds(e)
            logger.warning(
                "Rate limit hit (attempt %d/%d); backing off %.1fs",
                attempt + 1, attempts, backoff,
            )
            time.sleep(backoff)
            last_error = e
    if last_error is not None:
        raise last_error
