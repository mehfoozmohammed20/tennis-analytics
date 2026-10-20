"""
Extraction stage: pulls raw JSON from all 3 SportRadar tennis endpoints
and saves each to data/raw/ for the transform stage to consume.
"""
import json
import os
from datetime import datetime

from api.competitions import get_competitions
from api.complexes import get_complexes
from api.rankings import get_doubles_rankings
from api.client import SportRadarAPIError
from api.config import get_logger

logger = get_logger(__name__)

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
ARCHIVE_DIR = os.path.join(RAW_DIR, "archive")


def save_raw(name: str, data: dict) -> str:
    """
    Saves the latest payload as data/raw/<name>.json (read by later stages) AND an
    immutable timestamped copy in data/raw/archive/ so every run stays reproducible.
    """
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    path = os.path.join(RAW_DIR, f"{name}.json")
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    archive_path = os.path.join(ARCHIVE_DIR, f"{name}_{stamp}.json")
    for target in (path, archive_path):
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {name} -> {path} (archived copy: {os.path.basename(archive_path)})")
    return path


def run_extraction() -> dict:
    """
    Runs all 3 extractions. Returns dict of {endpoint_name: raw_json}.
    Continues on individual endpoint failure so a single bad fetch
    doesn't block the others; logs and re-raises only if ALL fail.
    """
    results = {}
    errors = []

    fetchers = {
        "competitions": get_competitions,
        "complexes": get_complexes,
        "doubles_rankings": get_doubles_rankings,
    }

    for name, fetch_fn in fetchers.items():
        try:
            data = fetch_fn()
            save_raw(name, data)
            results[name] = data
        except SportRadarAPIError as e:
            logger.error(f"Extraction failed for {name}: {e}")
            errors.append(name)

    if len(errors) == len(fetchers):
        raise SportRadarAPIError("All endpoint extractions failed. Check API key / connectivity.")

    if errors:
        logger.warning(f"Partial extraction success. Failed: {errors}")

    return results


if __name__ == "__main__":
    logger.info(f"Starting extraction run at {datetime.now().isoformat()}")
    run_extraction()
    logger.info("Extraction complete.")
