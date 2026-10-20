"""
Central config for SportRadar Tennis API access.
Loads API key/base URL from .env — never hard-code credentials.
"""
import os
import logging
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

API_KEY = os.getenv("SPORTRADAR_API_KEY")
BASE_URL = os.getenv("SPORTRADAR_BASE_URL", "https://api.sportradar.com/tennis/trial/v3/en")

if not API_KEY:
    raise EnvironmentError(
        f"SPORTRADAR_API_KEY not found. Expected a file named .env in {PROJECT_ROOT} "
        "(copy .env.example to .env and add your key)."
    )

REQUEST_TIMEOUT = 15  # seconds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
