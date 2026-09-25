"""Make the project root importable regardless of where pytest is invoked."""

import os
import sys
from pathlib import Path

os.environ["APP_ENV"] = "development"
os.environ["JOB_BACKEND"] = "memory"
os.environ["AUTH_REQUIRED"] = "false"
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
