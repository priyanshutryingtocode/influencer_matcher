"""Central configuration: model names, defaults, and environment loading.

Keeping these in one place means swapping a model version, or later moving
to Vertex AI instead of the Gemini Developer API, only touches this file.
"""

import os

from dotenv import load_dotenv

load_dotenv()  # reads a local .env file if present, no-op otherwise

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

EMBED_MODEL = "gemini-embedding-001"
GEN_MODEL = "gemini-2.5-flash"

# Gemini Embedding defaults to 3072 dims; 768 is a good quality/cost tradeoff
# for a project this size. Bump to 1536 or 3072 once you're on real data and
# want maximum retrieval quality.
EMBED_DIMENSIONS = 768

DEFAULT_INFLUENCER_COUNT = 60
DEFAULT_TOP_K_RETRIEVAL = 10
DEFAULT_TOP_N_RANKED = 5
