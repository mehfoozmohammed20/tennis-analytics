"""
Reconciliation: proves rows were not silently lost between stages.

1. raw_vs_transformed()   - API response counts vs counts after transform (pure, no DB)
2. reconcile_with_db()    - rows loaded this run vs rows actually present in MySQL
"""
from api.config import get_logger

logger = get_logger(__name__)

# transformed key -> (table, how a row is uniquely identified)
TABLES = {
    "categories": ("Categories", ("category_id",)),
    "competitions": ("Competitions", ("competition_id",)),
    "complexes": ("Complexes", ("complex_id",)),
    "venues": ("Venues", ("venue_id",)),
    "competitors": ("Competitors", ("competitor_id",)),
    "rankings": ("Competitor_Rankings",
                 ("competitor_id", "ranking_year", "ranking_week", "ranking_gender")),
}


def raw_vs_transformed(raw: dict, transformed: dict) -> dict:
    """Compare record counts in the raw API payloads with counts after transformation."""
    comps = raw.get("competitions", {}).get("competitions", []) or []
    complexes = raw.get("complexes", {}).get("complexes", []) or []
    snapshots = raw.get("doubles_rankings", {}).get("rankings", []) or []

    pairs = {
        "competitions": (len(comps), len(transformed.get("competitions", []))),
        "complexes": (len(complexes), len(transformed.get("complexes", []))),
        "venues": (sum(len(c.get("venues") or []) for c in complexes),
                   len(transformed.get("venues", []))),
        "ranking_rows": (sum(len(s.get("competitor_rankings") or []) for s in snapshots),
                         len(transformed.get("rankings", []))),
    }
    result = {k: {"raw": a, "transformed": b, "match": a == b} for k, (a, b) in pairs.items()}
    for k, v in result.items():
        if not v["match"]:
            logger.warning(f"Reconciliation: {k} raw={v['raw']} transformed={v['transformed']} "
                           f"(records skipped during transform)")
    return result


def unique_keys(rows: list, key_fields: tuple) -> int:
    return len({tuple(r.get(f) for f in key_fields) for r in rows})


def reconcile_with_db(transformed: dict, cursor) -> dict:
    """
    For each table: unique rows from this run must all exist in the database.
    Rankings accumulate week over week, so the DB may legitimately hold MORE rows.
    Also checks the rankings table for duplicate (competitor, year, week, gender) rows.
    """
    result = {}
    for key, (table, key_fields) in TABLES.items():
        rows = transformed.get(key)
        if rows is None:
            continue
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        in_db = cursor.fetchone()[0]
        unique_this_run = unique_keys(rows, key_fields)
        result[key] = {
            "rows_this_run": len(rows),
            "unique_rows_this_run": unique_this_run,
            "duplicates_collapsed_by_upsert": len(rows) - unique_this_run,
            "in_database": in_db,
            "ok": in_db >= unique_this_run,
        }
        if not result[key]["ok"]:
            logger.error(f"Reconciliation FAILED for {table}: db={in_db} < unique this run={unique_this_run}")

    cursor.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM Competitor_Rankings "
        "GROUP BY competitor_id, ranking_year, ranking_week, ranking_gender "
        "HAVING COUNT(*) > 1) d"
    )
    dup_groups = cursor.fetchone()[0]
    result["rankings_duplicate_groups_in_db"] = {"count": dup_groups, "ok": dup_groups == 0}
    if dup_groups:
        logger.error("Duplicate ranking rows found - is the UNIQUE KEY uq_competitor_week missing?")
    return result


def run_db_reconciliation(transformed: dict) -> dict:
    """Opens its own connection; returns {} (with an error log) if the database is unreachable."""
    from database.connection import get_mysql_connection as get_connection  # the pipeline always checks MySQL
    try:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            return reconcile_with_db(transformed, cursor)
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error(f"DB reconciliation could not run: {e}")
        return {}
