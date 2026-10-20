"""
Transform stage: converts raw nested JSON (from data/raw/) into flat
relational records matching the SQL schema (database/schema.sql).

Handles:
- missing/optional fields (parent_id, level, venues array)
- nested objects (category, competitor)
- dedup of shared entities (categories, complexes appear repeated across records)
"""
from api.config import get_logger

logger = get_logger(__name__)


def transform_competitions(raw: dict) -> dict:
    """
    Input: raw competitions.json dict
    Output: {"categories": [...], "competitions": [...]}
    """
    categories = {}
    competitions = []

    for comp in raw.get("competitions", []):
        category = comp.get("category", {})
        cat_id = category.get("id")

        if cat_id and cat_id not in categories:
            categories[cat_id] = {
                "category_id": cat_id,
                "category_name": category.get("name", "Unknown"),
            }

        if not comp.get("id"):
            logger.warning(f"Skipping competition with missing id: {comp}")
            continue

        competitions.append({
            "competition_id": comp["id"],
            "competition_name": comp.get("name", "Unknown"),
            "parent_id": comp.get("parent_id"),  # nullable, top-level comps have none
            "type": comp.get("type", "unknown"),
            "gender": comp.get("gender", "unknown"),
            "category_id": cat_id,
            # In the actual API response `level` (e.g. grand_slam, atp_250) sits on the
            # competition object itself, next to `category` — not inside it. Fall back to
            # category.level in case the API ever nests it there. Nullable: not always present.
            "category_level": comp.get("level") or category.get("level"),
        })

    logger.info(f"Transformed {len(categories)} categories, {len(competitions)} competitions")
    return {"categories": list(categories.values()), "competitions": competitions}


def transform_complexes(raw: dict) -> dict:
    """
    Input: raw complexes.json dict
    Output: {"complexes": [...], "venues": [...]}
    """
    complexes = []
    venues = []

    for cx in raw.get("complexes", []):
        if not cx.get("id"):
            logger.warning(f"Skipping complex with missing id: {cx}")
            continue

        complexes.append({
            "complex_id": cx["id"],
            "complex_name": cx.get("name", "Unknown"),
        })

        # Some complexes have no venues key at all (observed in actual API data)
        for v in cx.get("venues", []):
            if not v.get("id"):
                logger.warning(f"Skipping venue with missing id under complex {cx['id']}")
                continue

            venues.append({
                "venue_id": v["id"],
                "venue_name": v.get("name", "Unknown"),
                "city_name": v.get("city_name", "Unknown"),
                "country_name": v.get("country_name", "Unknown"),
                "country_code": v.get("country_code", "N/A"),
                "timezone": v.get("timezone", "Unknown"),
                "complex_id": cx["id"],
            })

    logger.info(f"Transformed {len(complexes)} complexes, {len(venues)} venues")
    return {"complexes": complexes, "venues": venues}


def transform_rankings(raw: dict) -> dict:
    """
    Input: raw doubles rankings.json dict
    Output: {"competitors": [...], "rankings": [...]}

    Note: API returns rankings nested under a snapshot object (year/week/gender)
    rather than flat rows as the original spec assumed. Snapshot context is
    denormalized onto each ranking row (ranking_year/week/gender columns).
    """
    competitors = {}
    rankings = []

    for snapshot in raw.get("rankings", []):
        year = snapshot.get("year")
        week = snapshot.get("week")
        gender = snapshot.get("gender", "unknown")

        for entry in snapshot.get("competitor_rankings", []):
            competitor = entry.get("competitor", {})
            comp_id = competitor.get("id")

            if not comp_id:
                logger.warning(f"Skipping ranking entry with missing competitor id: {entry}")
                continue

            if comp_id not in competitors:
                competitors[comp_id] = {
                    "competitor_id": comp_id,
                    "name": competitor.get("name", "Unknown"),
                    "country": competitor.get("country", "Unknown"),
                    "country_code": competitor.get("country_code", "N/A"),
                    "abbreviation": competitor.get("abbreviation", "N/A"),
                }

            rankings.append({
                "rank": entry.get("rank"),
                "movement": entry.get("movement", 0),
                "points": entry.get("points", 0),
                "competitions_played": entry.get("competitions_played", 0),
                "ranking_year": year,
                "ranking_week": week,
                "ranking_gender": gender,
                "competitor_id": comp_id,
            })

    logger.info(f"Transformed {len(competitors)} competitors, {len(rankings)} ranking rows")
    return {"competitors": list(competitors.values()), "rankings": rankings}


def run_transformation(raw_data: dict) -> dict:
    """
    raw_data: {"competitions": {...}, "complexes": {...}, "doubles_rankings": {...}}
    Returns dict of all 6 table datasets, ready for validation/load.
    """
    out = {}

    if "competitions" in raw_data:
        out.update(transform_competitions(raw_data["competitions"]))
    if "complexes" in raw_data:
        out.update(transform_complexes(raw_data["complexes"]))
    if "doubles_rankings" in raw_data:
        out.update(transform_rankings(raw_data["doubles_rankings"]))

    return out
