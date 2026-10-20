"""
Validation stage: checks transformed data for integrity issues before
loading into SQL. Never fabricates stats — reports only what it actually finds.

Checks are tiered by severity:
- CRITICAL: would corrupt analysis if left in (duplicate PKs, negative points/rank,
  missing required names). These should block or be fixed before trusting results.
- INFORMATIONAL: real but harmless characteristics of the data (e.g. SportRadar's
  parent_id referencing a grouping ID outside this endpoint). Flagged for
  transparency, never treated as something to "fix".
"""
from api.config import get_logger

logger = get_logger(__name__)

# Keys in a table's report dict that are informational, not critical — extend as needed
INFORMATIONAL_KEYS = {"orphan_parent_refs"}


def validate_dataset(data: dict) -> dict:
    """
    data: output of etl.transform.run_transformation()
    Returns a report dict: {table_name: {issue_type: [details], "_severity": {...}}}
    Does not mutate input data — caller decides how to handle flagged rows.
    """
    report = {}

    # --- Categories ---
    cat_ids = [c["category_id"] for c in data.get("categories", [])]
    report["categories"] = {
        "total": len(cat_ids),
        "duplicate_ids": _find_duplicates(cat_ids),
        "missing_name": [c["category_id"] for c in data.get("categories", []) if not c.get("category_name")],
    }

    # --- Competitions ---
    comp_ids = [c["competition_id"] for c in data.get("competitions", [])]
    comp_id_set = set(comp_ids)
    orphan_parents = [
        c["competition_id"] for c in data.get("competitions", [])
        if c.get("parent_id") and c["parent_id"] not in comp_id_set
    ]
    orphan_categories = [
        c["competition_id"] for c in data.get("competitions", [])
        if c.get("category_id") not in set(cat_ids)
    ]
    report["competitions"] = {
        "total": len(comp_ids),
        "duplicate_ids": _find_duplicates(comp_ids),
        "missing_name": [c["competition_id"] for c in data.get("competitions", []) if not c.get("competition_name")],
        # informational: SportRadar's parent_id points to a season/grouping ID that's
        # a different entity type than what /competitions.json returns — expected, not a bug
        "orphan_parent_refs": orphan_parents,
        "orphan_category_refs": orphan_categories,
    }

    # --- Complexes ---
    complex_ids = [c["complex_id"] for c in data.get("complexes", [])]
    report["complexes"] = {
        "total": len(complex_ids),
        "duplicate_ids": _find_duplicates(complex_ids),
    }

    # --- Venues ---
    venue_ids = [v["venue_id"] for v in data.get("venues", [])]
    orphan_venue_complex = [
        v["venue_id"] for v in data.get("venues", [])
        if v.get("complex_id") not in set(complex_ids)
    ]
    bad_country_codes = [
        v["venue_id"] for v in data.get("venues", [])
        if not v.get("country_code") or len(v["country_code"]) != 3
    ]
    report["venues"] = {
        "total": len(venue_ids),
        "duplicate_ids": _find_duplicates(venue_ids),
        "orphan_complex_refs": orphan_venue_complex,
        "invalid_country_code": bad_country_codes,
    }

    # --- Competitors ---
    competitor_ids = [c["competitor_id"] for c in data.get("competitors", [])]
    report["competitors"] = {
        "total": len(competitor_ids),
        "duplicate_ids": _find_duplicates(competitor_ids),
        "missing_name": [c["competitor_id"] for c in data.get("competitors", []) if not c.get("name")],
    }

    # --- Rankings ---
    rankings = data.get("rankings", [])
    orphan_ranking_competitor = [
        r for r in rankings if r.get("competitor_id") not in set(competitor_ids)
    ]
    invalid_points = [r for r in rankings if r.get("points") is None or r["points"] < 0]
    invalid_rank = [r for r in rankings if r.get("rank") is None or r["rank"] < 1]
    report["rankings"] = {
        "total": len(rankings),
        "orphan_competitor_refs": len(orphan_ranking_competitor),
        "invalid_points": len(invalid_points),
        "invalid_rank": len(invalid_rank),
        "note": "duplicate ranks (ties) are valid, not flagged as an issue",
    }

    _tag_severity(report)
    _log_report(report)
    return report


def _tag_severity(report: dict):
    """Adds a '_severity' summary to each table's report: counts of critical vs informational issues."""
    for table, checks in report.items():
        critical = {}
        informational = {}
        for k, v in checks.items():
            if k in ("total", "note", "_severity") or not v:
                continue
            (informational if k in INFORMATIONAL_KEYS else critical)[k] = v
        checks["_severity"] = {
            "has_critical_issues": bool(critical),
            "critical_keys": list(critical.keys()),
            "informational_keys": list(informational.keys()),
        }


def is_clean(report: dict) -> bool:
    """True if no table has any CRITICAL issues (informational-only issues don't count)."""
    return not any(checks.get("_severity", {}).get("has_critical_issues") for checks in report.values())


def _find_duplicates(id_list: list) -> list:
    seen, dupes = set(), set()
    for i in id_list:
        if i in seen:
            dupes.add(i)
        seen.add(i)
    return list(dupes)


def _log_report(report: dict):
    for table, checks in report.items():
        sev = checks.get("_severity", {})
        if sev.get("has_critical_issues"):
            logger.warning(f"[{table}] CRITICAL issues found: {sev['critical_keys']}")
        elif sev.get("informational_keys"):
            logger.info(f"[{table}] passed critical checks, {checks.get('total', 0)} records "
                        f"(informational flags: {sev['informational_keys']})")
        else:
            logger.info(f"[{table}] passed validation, {checks.get('total', 0)} records")
