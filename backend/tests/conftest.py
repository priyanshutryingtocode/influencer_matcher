"""Make the project root importable regardless of where pytest is invoked."""

import os
import sys
from pathlib import Path

import pytest

os.environ["APP_ENV"] = "development"
os.environ["AUTH_REQUIRED"] = "false"
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail loudly if any test tries to build a real Gemini client.

    A test once took the `fake_api` fixture without calling it -- the fixture
    only *returns* an installer -- so it ran against the production endpoint and
    quietly spent the daily free-tier embedding quota on every full-suite run.
    The failure it eventually produced was a 429 from Google, not a wrong
    assertion, which is exactly the kind of thing that goes unnoticed for a long
    time.

    Every module that needs a client did `from .gemini_client import get_client`,
    which binds a module-local name at import time. Patching
    `gemini_client.get_client` alone therefore did nothing, and the test still
    reached the network -- verified by removing the fake_api() call and watching
    the real quota error come back. So each of those names is patched too.
    """
    from src import embeddings, gemini_client, match_service

    def refuse(*args, **kwargs):
        raise AssertionError(
            "a test tried to build a real Gemini client. Stub "
            "embeddings.get_embedding_client (the fake_api fixture does this) "
            "instead of calling into the network."
        )

    for module in (gemini_client, embeddings, match_service):
        if hasattr(module, "get_client"):
            monkeypatch.setattr(module, "get_client", refuse)

    from api.jobs import manager

    if hasattr(manager, "get_client"):
        monkeypatch.setattr(manager, "get_client", refuse)
