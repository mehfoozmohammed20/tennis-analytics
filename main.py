"""
Runs the full pipeline:
extract -> profile -> transform -> validate -> load -> views -> reconcile -> report

Saves data/quality_report.json (shown on the app's Data Quality page) and writes one
row per run to the ETL_Run_Log table.
Usage: python main.py
"""
import json
import os
from datetime import datetime

from etl.extract import run_extraction
from etl.profile import profile_raw
from etl.transform import run_transformation
from etl.validate import validate_dataset, is_clean
from etl.load import run_load, apply_views, log_run
from etl.reconcile import raw_vs_transformed, run_db_reconciliation
from api.config import get_logger

logger = get_logger(__name__)

QUALITY_REPORT_PATH = os.path.join(os.path.dirname(__file__), "data", "quality_report.json")

# If True, a CRITICAL validation issue (duplicate keys, negative points...) stops the load
BLOCK_LOAD_ON_CRITICAL = True


class CriticalValidationError(Exception):
    pass


def save_quality_report(report: dict) -> None:
    os.makedirs(os.path.dirname(QUALITY_REPORT_PATH), exist_ok=True)
    with open(QUALITY_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"Saved data quality report -> {QUALITY_REPORT_PATH}")


def main() -> dict:
    started = datetime.now()
    report = {"run_at": started.isoformat()}
    logger.info("=== ETL PIPELINE START ===")

    try:
        logger.info("Stage 1/7: Extraction")
        raw = run_extraction()

        logger.info("Stage 2/7: Profiling raw data")
        report["profile"] = profile_raw(raw)

        logger.info("Stage 3/7: Transformation")
        transformed = run_transformation(raw)
        report["raw_vs_transformed"] = raw_vs_transformed(raw, transformed)
        report["loaded_counts"] = {k: len(v) for k, v in transformed.items()}

        logger.info("Stage 4/7: Validation")
        report["validation"] = validate_dataset(transformed)
        if BLOCK_LOAD_ON_CRITICAL and not is_clean(report["validation"]):
            raise CriticalValidationError("Critical validation issues found - load aborted. "
                                          "See validation section of the quality report.")

        logger.info("Stage 5/7: Load")
        run_load(transformed)

        logger.info("Stage 6/7: Analytical views")
        report["views"] = apply_views()

        logger.info("Stage 7/7: Reconciliation against the database")
        report["db_reconciliation"] = run_db_reconciliation(transformed)

        report["status"] = "SUCCESS"
        logger.info("=== ETL PIPELINE COMPLETE ===")
    except Exception as e:
        report["status"] = "FAILED"
        report["error"] = str(e)
        logger.error(f"=== ETL PIPELINE FAILED: {e} ===")
        save_quality_report(report)
        log_run("FAILED", {"error": str(e), "started": started.isoformat()})
        raise

    report["duration_seconds"] = round((datetime.now() - started).total_seconds(), 1)
    save_quality_report(report)
    log_run("SUCCESS", {
        "started": started.isoformat(),
        "duration_seconds": report["duration_seconds"],
        "loaded_counts": report["loaded_counts"],
        "views": report.get("views"),
    })
    return report


if __name__ == "__main__":
    main()
