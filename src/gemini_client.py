"""Gemini API client factory."""

from google import genai
from google.genai import types

from . import config


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
