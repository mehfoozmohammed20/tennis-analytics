"""
Tests for etl.validate — duplicate detection, FK integrity, invalid value checks.
Run: pytest tests/test_validate.py -v
"""
from etl.validate import validate_dataset, _find_duplicates


def test_find_duplicates():
    assert _find_duplicates(["a", "b", "a", "c"]) == ["a"]
    assert _find_duplicates(["a", "b", "c"]) == []


def test_validate_catches_duplicate_category_ids():
    data = {"categories": [
        {"category_id": "sr:category:1", "category_name": "ATP"},
        {"category_id": "sr:category:1", "category_name": "ATP Dup"},
    ]}
    report = validate_dataset(data)
    assert "sr:category:1" in report["categories"]["duplicate_ids"]


def test_validate_catches_orphan_parent_ref():
    data = {"competitions": [
        {"competition_id": "sr:competition:1", "competition_name": "Child",
         "parent_id": "sr:competition:MISSING", "category_id": "sr:category:1"}
    ], "categories": [{"category_id": "sr:category:1", "category_name": "ATP"}]}
    report = validate_dataset(data)
    assert "sr:competition:1" in report["competitions"]["orphan_parent_refs"]


def test_validate_catches_orphan_venue_complex_ref():
    data = {"venues": [
        {"venue_id": "sr:venue:1", "country_code": "USA", "complex_id": "sr:complex:MISSING"}
    ], "complexes": []}
    report = validate_dataset(data)
    assert "sr:venue:1" in report["venues"]["orphan_complex_refs"]


def test_validate_catches_invalid_country_code():
    data = {"venues": [
        {"venue_id": "sr:venue:1", "country_code": "US", "complex_id": None}
    ]}
    report = validate_dataset(data)
    assert "sr:venue:1" in report["venues"]["invalid_country_code"]


def test_validate_catches_negative_points_and_rank():
    data = {"rankings": [
        {"rank": -1, "points": -50, "competitor_id": "sr:competitor:1"}
    ], "competitors": [{"competitor_id": "sr:competitor:1", "name": "X"}]}
    report = validate_dataset(data)
    assert report["rankings"]["invalid_points"] == 1
    assert report["rankings"]["invalid_rank"] == 1


def test_validate_does_not_flag_tied_ranks_as_duplicates():
    # Two competitors legitimately sharing rank 15 — this should NOT be flagged as an error
    data = {
        "competitors": [
            {"competitor_id": "sr:competitor:1", "name": "A"},
            {"competitor_id": "sr:competitor:2", "name": "B"},
        ],
        "rankings": [
            {"rank": 15, "points": 100, "competitor_id": "sr:competitor:1"},
            {"rank": 15, "points": 100, "competitor_id": "sr:competitor:2"},
        ],
    }
    report = validate_dataset(data)
    # no "duplicate_rank" key should exist / be flagged — ties are valid
    assert "duplicate_ranks" not in report["rankings"]
    assert report["rankings"]["invalid_rank"] == 0


def test_validate_clean_data_no_issues():
    data = {
        "categories": [{"category_id": "sr:category:1", "category_name": "ATP"}],
        "competitions": [{"competition_id": "sr:competition:1", "competition_name": "Test",
                           "parent_id": None, "category_id": "sr:category:1"}],
        "complexes": [{"complex_id": "sr:complex:1", "complex_name": "Test Complex"}],
        "venues": [{"venue_id": "sr:venue:1", "country_code": "USA", "complex_id": "sr:complex:1"}],
        "competitors": [{"competitor_id": "sr:competitor:1", "name": "Player"}],
        "rankings": [{"rank": 1, "points": 100, "competitor_id": "sr:competitor:1"}],
    }
    report = validate_dataset(data)
    assert report["categories"]["duplicate_ids"] == []
    assert report["competitions"]["orphan_parent_refs"] == []
    assert report["venues"]["orphan_complex_refs"] == []
    assert report["rankings"]["invalid_points"] == 0
