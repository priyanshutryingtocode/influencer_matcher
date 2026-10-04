"""Gemini API client factory, shared by ranking and embedding calls."""

import json
import logging
import re
import time

from google import genai
from google.genai import errors, types

from . import config

logger = logging.getLogger(__name__)

_RETRY_MESSAGE_MS = re.compile(r"Please retry in ([\d.]+)s", re.IGNORECASE)
_DAILY_QUOTA_RE = re.compile(r"[A-Za-z0-9_-]*[Pp]er_?[Dd]ay[A-Za-z0-9_-]*")
_QUOTA_VALUE_RE = re.compile(r"quota'?\"?\s*Value\s*\"?\s*[:=]\s*\"?(\d+)", re.IGNORECASE)
_DAILY_RESET_HINT = "The counter resets at midnight Pacific; retrying now cannot help."


class DailyQuotaExhausted(RuntimeError):
    """A per-day request quota is spent.

    Distinct from a per-minute throttle: the delay the server suggests is
    meaningless here, because the counter only refills on a daily boundary.
    Raising this instead of sleeping keeps a bulk job from stalling for a
    minute before failing anyway.
    """

    def __init__(self, label: str, quota_id: str, quota_value: int | None = None):
        limit = f" of {quota_value} requests/day" if quota_value else ""
        super().__init__(
            f"{label} exhausted its daily free-tier quota ({quota_id}{limit}). "
            f"{_DAILY_RESET_HINT}"
        )
        self.label = label
        self.quota_id = quota_id
        self.quota_value = quota_value


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


def _searchable_text(error: Exception) -> str:
    """Flatten an SDK error so quota ids buried in the payload can be matched.

    google-genai keeps the response body on `details`, and the useful
    identifiers (quotaMetric, quotaId, quotaValue) only appear inside the
    structured QuotaFailure list, not always in the human-readable message.
    """
    chunks = [str(error), str(getattr(error, "message", "") or "")]
    details = getattr(error, "details", None)
    if isinstance(details, (dict, list)):
        try:
            chunks.append(json.dumps(details, default=str))
        except (TypeError, ValueError):
            pass
    return " ".join(chunks)


def _daily_quota(error: Exception) -> tuple[str, int | None] | None:
    """Return (quota id, quota value) if this 429 is a per-day cap, else None."""
    text = _searchable_text(error)
    marker = _DAILY_QUOTA_RE.search(text)
    if not marker:
        return None
    value = _QUOTA_VALUE_RE.search(text)
    try:
        limit = int(value.group(1)) if value else None
    except ValueError:
        limit = None
    return marker.group(0), limit


def _retry_on_throttle(call, *, attempts: int, label: str):
    """Run `call`, retrying only 429 RESOURCE_EXHAUSTED quota throttles.

    A 429 is a quota throttle, not an outage: sleep the server-provided delay,
    then retry, up to `attempts`. Any other error is re-raised unchanged so
    callers keep their existing error handling and fallbacks.

    A per-day cap is the one exception: the suggested delay cannot help, so it
    is raised as DailyQuotaExhausted immediately instead of burning the run's
    time budget on sleeps that are bound to fail.
    """
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return call()
        except errors.ClientError as e:
            ctx = f"{getattr(e, 'code', '')} {getattr(e, 'message', '')} {str(e)}"
            is_throttle = "429" in ctx and "RESOURCE_EXHAUSTED" in ctx
            if is_throttle:
                daily = _daily_quota(e)
                if daily is not None:
                    raise DailyQuotaExhausted(label, daily[0], daily[1]) from e
            if not is_throttle or attempt == attempts - 1:
                raise
            backoff = _throttle_sleep_seconds(e)
            logger.warning(
                "%s rate limit hit (attempt %d/%d); backing off %.1fs",
                label, attempt + 1, attempts, backoff,
            )
            time.sleep(backoff)
            last_error = e
    if last_error is not None:
        raise last_error


def generate_content_throttled(
    client,
    model: str,
    contents,
    gen_config: types.GenerateContentConfig | None = None,
    attempts: int | None = None,
):
    """Call generate_content under the shared quota-throttle policy."""
    attempts = config.GEMINI_RETRY_ATTEMPTS if attempts is None else attempts
    return _retry_on_throttle(
        lambda: client.models.generate_content(model=model, contents=contents, config=gen_config),
        attempts=attempts,
        label=f"generate_content({model})",
    )


def embed_content_throttled(
    client,
    model: str,
    text: str,
    *,
    task_type: str,
    output_dimensionality: int,
    attempts: int | None = None,
):
    """Embed one text under the shared quota-throttle policy.

    gemini-embedding-001 takes a single content per request, so batching is the
    caller's responsibility.
    """
    attempts = config.GEMINI_RETRY_ATTEMPTS if attempts is None else attempts
    embed_config = types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=output_dimensionality,
    )
    return _retry_on_throttle(
        lambda: client.models.embed_content(model=model, contents=text, config=embed_config),
        attempts=attempts,
        label=f"embed_content({model})",
    )
