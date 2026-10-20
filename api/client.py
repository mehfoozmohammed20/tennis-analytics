"""
Shared HTTP client for hitting SportRadar Tennis API endpoints.
Handles timeouts, HTTP errors, rate limits, and empty/invalid responses.
"""
import time
import requests

from api.config import API_KEY, BASE_URL, REQUEST_TIMEOUT, get_logger

logger = get_logger(__name__)


class SportRadarAPIError(Exception):
    pass


def fetch_endpoint(endpoint: str, max_retries: int = 3, backoff: float = 2.0) -> dict:
    """
    Fetch a SportRadar tennis endpoint (e.g. 'complexes', 'competitions').
    Returns parsed JSON dict. Raises SportRadarAPIError on unrecoverable failure.
    """
    url = f"{BASE_URL}/{endpoint}.json"
    params = {"api_key": API_KEY}

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

            if response.status_code == 429:
                wait = backoff * attempt
                logger.warning(f"Rate limited on {endpoint}, retrying in {wait}s (attempt {attempt})")
                time.sleep(wait)
                continue

            response.raise_for_status()

            data = response.json()
            if not data:
                raise SportRadarAPIError(f"Empty response body from {endpoint}")

            logger.info(f"Fetched {endpoint} successfully")
            return data

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on {endpoint}, attempt {attempt}/{max_retries}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error on {endpoint}, attempt {attempt}/{max_retries}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error on {endpoint}: {e}")
            raise SportRadarAPIError(f"HTTP error fetching {endpoint}: {e}") from e
        except ValueError as e:
            logger.error(f"Invalid JSON from {endpoint}: {e}")
            raise SportRadarAPIError(f"Invalid JSON from {endpoint}: {e}") from e

        time.sleep(backoff * attempt)

    raise SportRadarAPIError(f"Failed to fetch {endpoint} after {max_retries} attempts")
