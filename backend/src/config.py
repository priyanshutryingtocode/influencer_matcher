"""Central configuration: model names, defaults, and environment loading.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

DATABASE_URL = os.environ.get("DATABASE_URL")
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
if APP_ENV not in {"development", "test", "demo", "production"}:
    raise RuntimeError("APP_ENV must be development, test, demo, or production")
AUTH_REQUIRED = os.environ.get("AUTH_REQUIRED", "true" if APP_ENV in {"demo", "production"} else "false").lower() == "true"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")
SUPABASE_JWKS_URL = os.environ.get("SUPABASE_JWKS_URL") or (
    f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else None
)
SUPABASE_ISSUER = os.environ.get("SUPABASE_ISSUER") or (f"{SUPABASE_URL.rstrip('/')}/auth/v1" if SUPABASE_URL else None)
SUPABASE_JWT_AUDIENCE = os.environ.get("SUPABASE_JWT_AUDIENCE", "authenticated")
JOB_BACKEND = os.environ.get("JOB_BACKEND", "postgres" if APP_ENV == "production" else "memory").lower()
RUN_SCHEMA_ON_STARTUP = os.environ.get("RUN_SCHEMA_ON_STARTUP", "false" if APP_ENV == "production" else "true").lower() == "true"
HF_HOME = os.environ.get("HF_HOME") or str(ROOT_DIR / "backend" / "model-cache")

GEN_MODEL = "gemini-2.5-flash-lite"

LOCAL_EMBED_MODEL = os.environ.get("LOCAL_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

EMBED_DIMENSIONS = int(os.environ.get("EMBED_DIMENSIONS", "384"))
if EMBED_DIMENSIONS <= 0:
    raise RuntimeError("EMBED_DIMENSIONS must be a positive integer")

EMBED_QUERY_PREFIX = os.environ.get("EMBED_QUERY_PREFIX", "")
EMBED_PASSAGE_PREFIX = os.environ.get("EMBED_PASSAGE_PREFIX", "")

DEFAULT_INFLUENCER_COUNT = 60
DEFAULT_TOP_K_RETRIEVAL = 10
DEFAULT_TOP_N_RANKED = 5

MAX_INFLUENCER_COUNT = 5000
MAX_TOP_K = 50
MAX_MEMORY_JOBS = int(os.environ.get("MAX_MEMORY_JOBS", "4"))
MAX_MATCH_JOBS_PER_USER_PER_HOUR = int(os.environ.get("MAX_MATCH_JOBS_PER_USER_PER_HOUR", "10"))
MAX_MATCH_JOBS_PER_IP_PER_HOUR = int(os.environ.get("MAX_MATCH_JOBS_PER_IP_PER_HOUR", "20"))
STALE_JOB_AFTER_SECONDS = int(os.environ.get("STALE_JOB_AFTER_SECONDS", "900"))
if (
    MAX_MEMORY_JOBS <= 0
    or MAX_MATCH_JOBS_PER_USER_PER_HOUR <= 0
    or MAX_MATCH_JOBS_PER_IP_PER_HOUR <= 0
    or STALE_JOB_AFTER_SECONDS <= 0
):
    raise RuntimeError("Job limits must be positive integers")

GEMINI_TIMEOUT_MS = 120_000
GEMINI_RETRY_ATTEMPTS = 3
