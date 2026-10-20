"""
Load stage: inserts transformed + validated data into MySQL.
Insert order respects foreign key dependencies:
Categories -> Competitions -> Complexes -> Venues -> Competitors -> Rankings
Uses INSERT ... ON DUPLICATE KEY UPDATE so reruns are idempotent (safe to re-load).
"""
import json
import os
import re

from database.connection import get_mysql_connection as get_connection  # the pipeline always writes to MySQL
from api.config import get_logger

logger = get_logger(__name__)


def load_categories(cursor, rows):
    sql = """
        INSERT INTO Categories (category_id, category_name)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE category_name = VALUES(category_name)
    """
    data = [(r["category_id"], r["category_name"]) for r in rows]
    cursor.executemany(sql, data)
    logger.info(f"Loaded {len(data)} categories")


def load_competitions(cursor, rows):
    sql = """
        INSERT INTO Competitions
            (competition_id, competition_name, parent_id, type, gender, category_id, category_level)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            competition_name = VALUES(competition_name),
            parent_id = VALUES(parent_id),
            type = VALUES(type),
            gender = VALUES(gender),
            category_id = VALUES(category_id),
            category_level = VALUES(category_level)
    """
    data = [
        (r["competition_id"], r["competition_name"], r.get("parent_id"),
         r["type"], r["gender"], r["category_id"], r.get("category_level"))
        for r in rows
    ]
    # FK checks disabled here because parent_id can reference a competition_id
    # not present in this same fetched page (insert-order issue) or a true
    # orphan (parent tournament not in the trial dataset at all — expected,
    # see validate.py orphan_parent_refs). Re-enabled immediately after.
    cursor.execute("SET FOREIGN_KEY_CHECKS=0")
    cursor.executemany(sql, data)
    cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    logger.info(f"Loaded {len(data)} competitions")


def load_complexes(cursor, rows):
    sql = """
        INSERT INTO Complexes (complex_id, complex_name)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE complex_name = VALUES(complex_name)
    """
    data = [(r["complex_id"], r["complex_name"]) for r in rows]
    cursor.executemany(sql, data)
    logger.info(f"Loaded {len(data)} complexes")


def load_venues(cursor, rows):
    sql = """
        INSERT INTO Venues
            (venue_id, venue_name, city_name, country_name, country_code, timezone, complex_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            venue_name = VALUES(venue_name),
            city_name = VALUES(city_name),
            country_name = VALUES(country_name),
            country_code = VALUES(country_code),
            timezone = VALUES(timezone),
            complex_id = VALUES(complex_id)
    """
    data = [
        (r["venue_id"], r["venue_name"], r["city_name"], r["country_name"],
         r["country_code"], r["timezone"], r["complex_id"])
        for r in rows
    ]
    cursor.executemany(sql, data)
    logger.info(f"Loaded {len(data)} venues")


def load_competitors(cursor, rows):
    sql = """
        INSERT INTO Competitors (competitor_id, name, country, country_code, abbreviation)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            country = VALUES(country),
            country_code = VALUES(country_code),
            abbreviation = VALUES(abbreviation)
    """
    data = [(r["competitor_id"], r["name"], r["country"], r["country_code"], r["abbreviation"]) for r in rows]
    cursor.executemany(sql, data)
    logger.info(f"Loaded {len(data)} competitors")


def load_rankings(cursor, rows):
    # Rankings are appended per (competitor, year, week) so multiple weekly runs
    # accumulate into real history instead of overwriting each other. This is what
    # makes trend analysis (movement over time) possible if the pipeline is run
    # on a schedule — a single run still only has one week's data, which is honest
    # and should be stated as a current limitation, not faked with synthetic weeks.
    sql = """
        INSERT INTO Competitor_Rankings
            (`rank`, movement, points, competitions_played, ranking_year, ranking_week, ranking_gender, competitor_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            `rank` = VALUES(`rank`),
            movement = VALUES(movement),
            points = VALUES(points),
            competitions_played = VALUES(competitions_played)
    """
    data = [
        (r["rank"], r["movement"], r["points"], r["competitions_played"],
         r["ranking_year"], r["ranking_week"], r["ranking_gender"], r["competitor_id"])
        for r in rows
    ]
    cursor.executemany(sql, data)
    logger.info(f"Loaded/updated {len(data)} ranking rows (appended by year/week, not wiped)")


def run_load(data: dict):
    """
    data: output of etl.transform.run_transformation()
    Rankings now use an upsert keyed on (competitor_id, year, week, gender), so
    re-running the pipeline for the same week updates in place, and running it
    on a new week adds new history rather than wiping the old snapshot.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if "categories" in data:
            load_categories(cursor, data["categories"])
        if "competitions" in data:
            load_competitions(cursor, data["competitions"])
        if "complexes" in data:
            load_complexes(cursor, data["complexes"])
        if "venues" in data:
            load_venues(cursor, data["venues"])
        if "competitors" in data:
            load_competitors(cursor, data["competitors"])

        if "rankings" in data:
            load_rankings(cursor, data["rankings"])

        conn.commit()
        logger.info("Load complete, transaction committed")

    except Exception as e:
        conn.rollback()
        logger.error(f"Load failed, rolled back: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------------------------
# Analytical views + run log
# ---------------------------------------------------------------------------
VIEWS_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "views.sql")


def split_sql_statements(sql_text: str) -> list:
    """Strip full-line '--' comments, then split on ';' into individual statements."""
    lines = [ln for ln in sql_text.splitlines() if not ln.strip().startswith("--")]
    return [stmt.strip() for stmt in "\n".join(lines).split(";") if stmt.strip()]


def apply_views(views_path: str = VIEWS_PATH) -> dict:
    """
    (Re)creates the analytical views. Never raises: a view problem must not undo a
    successful data load. Returns {"applied": n, "failed": [errors]}.
    """
    result = {"applied": 0, "failed": []}
    try:
        with open(views_path, "r", encoding="utf-8") as f:
            statements = split_sql_statements(f.read())
    except OSError as e:
        logger.error(f"Could not read views file: {e}")
        result["failed"].append(str(e))
        return result

    conn = get_connection()
    cursor = conn.cursor()
    try:
        for stmt in statements:
            try:
                cursor.execute(stmt)
                result["applied"] += 1
            except Exception as e:  # keep going so one bad view doesn't hide the rest
                logger.error(f"View creation failed: {e}")
                result["failed"].append(str(e))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    logger.info(f"Views applied: {result['applied']}, failed: {len(result['failed'])}")
    return result


RUN_LOG_DDL = """
    CREATE TABLE IF NOT EXISTS ETL_Run_Log (
        run_id   INT AUTO_INCREMENT PRIMARY KEY,
        run_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
        status   VARCHAR(20) NOT NULL,
        details  TEXT
    )
"""


def log_run(status: str, details: dict) -> None:
    """Best-effort: records one pipeline run (status + JSON details) in ETL_Run_Log."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(RUN_LOG_DDL)
        cursor.execute(
            "INSERT INTO ETL_Run_Log (status, details) VALUES (%s, %s)",
            (status, json.dumps(details, default=str)),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:  # logging a run must never crash the pipeline
        logger.error(f"Could not write ETL_Run_Log: {e}")
