"""Central configuration: model names, defaults, and environment loading.

Keeping these in one place means swapping a model version, or later moving
to Vertex AI instead of the Gemini Developer API, only touches this file.
"""

import os

from dotenv import load_dotenv

load_dotenv()  # reads a local .env file if present, no-op otherwise

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Supabase connection string, from Project Settings -> Database -> Connection
# string -> "Session pooler" (works over IPv4, recommended for local scripts
# like this one). Format looks like:
#   postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
DATABASE_URL = os.environ.get("DATABASE_URL")

EMBED_MODEL = "gemini-embedding-001"
GEN_MODEL = "gemini-2.5-flash"

# Gemini Embedding defaults to 3072 dims; 768 is a good quality/cost tradeoff
# for a project this size. Bump to 1536 or 3072 once you're on real data and
# want maximum retrieval quality.
EMBED_DIMENSIONS = 768

DEFAULT_INFLUENCER_COUNT = 60
DEFAULT_TOP_K_RETRIEVAL = 10
DEFAULT_TOP_N_RANKED = 5

# Hard ceilings so a mistyped CLI flag can't trigger an unexpectedly large
# (and unexpectedly expensive) batch of embedding/generation calls.
MAX_INFLUENCER_COUNT = 500
MAX_TOP_K = 50

# Gemini client resilience: fail fast instead of hanging, retry transient
# errors instead of crashing the whole run over one flaky request.
GEMINI_TIMEOUT_MS = 30_000
GEMINI_RETRY_ATTEMPTS = 3
