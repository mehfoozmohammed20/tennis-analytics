"""Test setup: the ETL modules read the API key at import time; tests never call the real API."""
import os

os.environ.setdefault("SPORTRADAR_API_KEY", "test-key-not-real")
