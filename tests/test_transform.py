"""
Tests for etl.transform — nested JSON flattening, missing/optional field handling.
Run: pytest tests/test_transform.py -v
"""
import pytest
from etl.transform import transform_competitions, transform_complexes, transform_rankings, run_transformation


def test_transform_competitions_basic():
    raw = {
        "competitions": [
            {"id": "sr:competition:1", "name": "Test Open", "type": "singles",
             "gender": "men", "category": {"id": "sr:category:1", "name": "ATP"}}
        ]
    }
    result = transform_competitions(raw)
    assert len(result["categories"]) == 1
    assert len(result["competitions"]) == 1
    assert result["competitions"][0]["parent_id"] is None
    assert result["competitions"][0]["category_level"] is None


def test_transform_competitions_dedupes_categories():
    raw = {
        "competitions": [
            {"id": "sr:competition:1", "name": "A", "type": "singles", "gender": "men",
             "category": {"id": "sr:category:1", "name": "ATP"}},
            {"id": "sr:competition:2", "name": "B", "type": "doubles", "gender": "men",
             "category": {"id": "sr:category:1", "name": "ATP"}},
        ]
    }
    result = transform_competitions(raw)
    assert len(result["categories"]) == 1  # deduped
    assert len(result["competitions"]) == 2


def test_transform_competitions_skips_missing_id():
    raw = {"competitions": [{"name": "No ID Comp", "type": "singles", "gender": "men", "category": {}}]}
    result = transform_competitions(raw)
    assert len(result["competitions"]) == 0


def test_transform_competitions_captures_level():
    # Matches the real API shape: `level` is a sibling of `category`, not nested inside it
    raw = {
        "competitions": [
            {"id": "sr:competition:1", "name": "Wimbledon", "type": "singles", "gender": "men",
             "category": {"id": "sr:category:3", "name": "ATP"}, "level": "grand_slam"}
        ]
    }
    result = transform_competitions(raw)
    assert result["competitions"][0]["category_level"] == "grand_slam"


def test_transform_competitions_level_fallback_to_category():
    raw = {
        "competitions": [
            {"id": "sr:competition:1", "name": "X", "type": "singles", "gender": "men",
             "category": {"id": "sr:category:3", "name": "ATP", "level": "atp_250"}}
        ]
    }
    result = transform_competitions(raw)
    assert result["competitions"][0]["category_level"] == "atp_250"


def test_transform_complexes_handles_missing_venues():
    raw = {"complexes": [{"id": "sr:complex:1", "name": "No Venues Complex"}]}
    result = transform_complexes(raw)
    assert len(result["complexes"]) == 1
    assert len(result["venues"]) == 0  # no crash on missing 'venues' key


def test_transform_complexes_basic():
    raw = {
        "complexes": [
            {"id": "sr:complex:1", "name": "Nacional",
             "venues": [{"id": "sr:venue:1", "name": "Court 1", "city_name": "Santiago",
                         "country_name": "Chile", "country_code": "CHL", "timezone": "America/Santiago"}]}
        ]
    }
    result = transform_complexes(raw)
    assert len(result["complexes"]) == 1
    assert len(result["venues"]) == 1
    assert result["venues"][0]["complex_id"] == "sr:complex:1"


def test_transform_rankings_flattens_snapshot():
    raw = {
        "rankings": [
            {"type_id": 2, "name": "ATP", "year": 2026, "week": 39, "gender": "men",
             "competitor_rankings": [
                 {"rank": 1, "movement": 0, "points": 1000, "competitions_played": 10,
                  "competitor": {"id": "sr:competitor:1", "name": "Test Player", "country": "USA",
                                 "country_code": "USA", "abbreviation": "TES"}}
             ]}
        ]
    }
    result = transform_rankings(raw)
    assert len(result["competitors"]) == 1
    assert len(result["rankings"]) == 1
    assert result["rankings"][0]["ranking_year"] == 2026
    assert result["rankings"][0]["ranking_week"] == 39


def test_transform_rankings_dedupes_competitors_across_snapshots():
    raw = {
        "rankings": [
            {"year": 2026, "week": 38, "gender": "men", "competitor_rankings": [
                {"rank": 1, "movement": 0, "points": 900, "competitions_played": 9,
                 "competitor": {"id": "sr:competitor:1", "name": "Player A", "country": "USA",
                                "country_code": "USA", "abbreviation": "PLA"}}
            ]},
            {"year": 2026, "week": 39, "gender": "men", "competitor_rankings": [
                {"rank": 1, "movement": 0, "points": 1000, "competitions_played": 10,
                 "competitor": {"id": "sr:competitor:1", "name": "Player A", "country": "USA",
                                "country_code": "USA", "abbreviation": "PLA"}}
            ]},
        ]
    }
    result = transform_rankings(raw)
    assert len(result["competitors"]) == 1   # same competitor, deduped
    assert len(result["rankings"]) == 2      # but 2 distinct ranking snapshots kept


def test_run_transformation_full_pipeline():
    raw_data = {
        "competitions": {"competitions": [
            {"id": "sr:competition:1", "name": "Test", "type": "singles", "gender": "men",
             "category": {"id": "sr:category:1", "name": "ATP"}}
        ]},
        "complexes": {"complexes": [{"id": "sr:complex:1", "name": "Test Complex"}]},
        "doubles_rankings": {"rankings": []},
    }
    result = run_transformation(raw_data)
    assert "categories" in result
    assert "competitions" in result
    assert "complexes" in result
    assert "venues" in result
    assert "competitors" in result
    assert "rankings" in result
