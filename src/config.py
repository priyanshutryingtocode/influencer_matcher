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

GEN_MODEL = "gemini-2.5-flash-lite"

# Embeddings are computed locally with Sentence Transformers (no API cost);
# this name is recorded per-row in the database's embed_model column so the
# provenance of stored vectors is always traceable.
LOCAL_EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"
# all-mpnet-base-v2 outputs 768-dim vectors. This must match the VECTOR(...)
# column width in vector_store.py -- changing the model means reindexing.
EMBED_DIMENSIONS = 768

# Some embedding families expect instruction prefixes (e5 wants "query: "/
# "passage: ", bge wants a search directive; mpnet wants nothing). These are
# prepended in embeddings.py before encoding. See README "Embedding model A/B".
EMBED_QUERY_PREFIX = ""
EMBED_PASSAGE_PREFIX = ""

DEFAULT_INFLUENCER_COUNT = 60
DEFAULT_TOP_K_RETRIEVAL = 10
DEFAULT_TOP_N_RANKED = 5

# Hard ceilings so a mistyped CLI flag can't trigger an unexpectedly large
# (and unexpectedly expensive) batch of embedding/generation calls.
MAX_INFLUENCER_COUNT = 1000
MAX_TOP_K = 50

# Gemini client resilience: fail fast instead of hanging, retry transient
# errors instead of crashing the whole run over one flaky request. The
# timeout is generous because a single ranking request may legitimately wait
# through a 429 rate-limit backoff (tens of seconds) before the model replies.
GEMINI_TIMEOUT_MS = 120_000
GEMINI_RETRY_ATTEMPTS = 3
