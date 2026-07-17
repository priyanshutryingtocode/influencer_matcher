"""Gemini API client factory."""

from google import genai

from . import config


def get_client() -> genai.Client:
    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your "
            "key, or export GEMINI_API_KEY directly. Get a key at "
            "https://aistudio.google.com/apikey"
        )
    return genai.Client(api_key=config.GEMINI_API_KEY)
