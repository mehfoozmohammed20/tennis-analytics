"""
Profiling stage: MEASURES the raw API data before it is transformed or loaded.

Every claim we make about the data (how many parents resolve, how many levels are
present, how many ties exist) should come from a number produced here, not from an
assumption. Output is saved in data/quality_report.json and shown in the app.
"""
import statistics
from collections import Counter

from api.config import get_logger

logger = get_logger(__name__)


def _pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 2) if whole else 0.0


def numeric_summary(values: list) -> dict:
    """Distribution summary + IQR outlier count for a list of numbers (None/non-numeric ignored)."""
    nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    out = {"count": len(nums), "null_or_invalid": len(values) - len(nums)}
    if not nums:
        return out
    nums_sorted = sorted(nums)
    if len(nums_sorted) >= 4:
        q1, _, q3 = statistics.quantiles(nums_sorted, n=4)
    else:
        q1 = q3 = statistics.median(nums_sorted)
    iqr = q3 - q1
    upper, lower = q3 + 1.5 * iqr, q1 - 1.5 * iqr
    out.update({
        "min": min(nums), "max": max(nums),
        "mean": round(statistics.mean(nums), 1),
        "median": statistics.median(nums_sorted),
        "q1": round(q1, 1), "q3": round(q3, 1),
        "iqr_upper_fence": round(upper, 1),
        "iqr_outliers": sum(1 for v in nums if v > upper or v < lower),
    })
    return out


def profile_competitions(data: dict) -> dict:
    comps = data.get("competitions", []) or []
    total = len(comps)
    ids = [c.get("id") for c in comps]
    id_set = {i for i in ids if i}
    with_parent = [c for c in comps if c.get("parent_id")]
    resolves = sum(1 for c in with_parent if c["parent_id"] in id_set)
    return {
        "total": total,
        "unique_ids": len(id_set),
        "missing_id": sum(1 for i in ids if not i),
        "missing_name": sum(1 for c in comps if not c.get("name")),
        "missing_category": sum(1 for c in comps if not (c.get("category") or {}).get("id")),
        "top_level_no_parent": total - len(with_parent),
        "with_parent_id": len(with_parent),
        "parent_id_resolves_in_dataset": resolves,
        "parent_id_unresolved": len(with_parent) - resolves,
        "parent_id_resolve_pct": _pct(resolves, len(with_parent)),
        "level_present": sum(1 for c in comps if c.get("level") or (c.get("category") or {}).get("level")),
        "level_values": dict(Counter(c.get("level") for c in comps if c.get("level")).most_common(15)),
        "type_values": dict(Counter(str(c.get("type")) for c in comps)),
        "gender_values": dict(Counter(str(c.get("gender")) for c in comps)),
    }


def profile_complexes(data: dict) -> dict:
    complexes = data.get("complexes", []) or []
    venues = [v for c in complexes for v in (c.get("venues") or [])]
    venue_ids = [v.get("id") for v in venues if v.get("id")]
    return {
        "complexes": len(complexes),
        "complexes_with_venues": sum(1 for c in complexes if c.get("venues")),
        "complexes_without_venues": sum(1 for c in complexes if not c.get("venues")),
        "venues": len(venues),
        "unique_venue_ids": len(set(venue_ids)),
        "venue_ids_repeated": len(venue_ids) - len(set(venue_ids)),
        "venues_missing_country_code": sum(1 for v in venues if not v.get("country_code")),
        "venues_missing_timezone": sum(1 for v in venues if not v.get("timezone")),
        "distinct_countries": len({v.get("country_name") for v in venues if v.get("country_name")}),
    }


def profile_rankings(data: dict) -> dict:
    snapshots = data.get("rankings", []) or []
    rows, per_snapshot, tied_rows = [], [], 0
    for s in snapshots:
        entries = s.get("competitor_rankings") or []
        rows.extend(entries)
        rank_counts = Counter(e.get("rank") for e in entries)
        tied_rows += sum(n for n in rank_counts.values() if n > 1)
        per_snapshot.append({
            "name": s.get("name"), "gender": s.get("gender"),
            "year": s.get("year"), "week": s.get("week"), "competitors": len(entries),
        })
    movements = [e.get("movement") for e in rows]
    return {
        "snapshots": per_snapshot,
        "ranking_rows": len(rows),
        "missing_competitor_id": sum(1 for e in rows if not (e.get("competitor") or {}).get("id")),
        "rows_sharing_a_rank_with_another_row": tied_rows,
        "movement_zero_pct": _pct(sum(1 for m in movements if m == 0), len(movements)),
        "points": numeric_summary([e.get("points") for e in rows]),
        "competitions_played": numeric_summary([e.get("competitions_played") for e in rows]),
    }


def profile_raw(raw: dict) -> dict:
    """raw: {"competitions": {...}, "complexes": {...}, "doubles_rankings": {...}} (any may be missing)."""
    report = {}
    if "competitions" in raw:
        report["competitions"] = profile_competitions(raw["competitions"])
    if "complexes" in raw:
        report["complexes"] = profile_complexes(raw["complexes"])
    if "doubles_rankings" in raw:
        report["rankings"] = profile_rankings(raw["doubles_rankings"])
    for name, sec in report.items():
        logger.info(f"Profiled {name}: {len(sec)} measures")
    return report
