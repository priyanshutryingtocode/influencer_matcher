"""Central configuration: model names, defaults, and environment loading.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

DATABASE_URL = os.environ.get("DATABASE_URL")

GEN_MODEL = "gemini-2.5-flash-lite"

LOCAL_EMBED_MODEL = "intfloat/e5-base-v2"

EMBED_DIMENSIONS = 768

EMBED_QUERY_PREFIX = "query: "
EMBED_PASSAGE_PREFIX = "passage: "

DEFAULT_INFLUENCER_COUNT = 60
DEFAULT_TOP_K_RETRIEVAL = 10
DEFAULT_TOP_N_RANKED = 5

MAX_INFLUENCER_COUNT = 5000
MAX_TOP_K = 50

GEMINI_TIMEOUT_MS = 120_000
GEMINI_RETRY_ATTEMPTS = 3
