"""Tests for etl.profile - measured facts about raw API data."""
from etl.profile import numeric_summary, profile_competitions, profile_complexes, profile_rankings


def test_numeric_summary_flags_outlier():
    s = numeric_summary([10, 11, 12, 13, 14, 15, 1000])
    assert s["count"] == 7
    assert s["max"] == 1000
    assert s["iqr_outliers"] == 1


def test_numeric_summary_ignores_none_and_empty():
    assert numeric_summary([None, None])["count"] == 0
    s = numeric_summary([5, None, 7])
    assert s["count"] == 2 and s["null_or_invalid"] == 1


def test_profile_competitions_parent_coverage():
    data = {"competitions": [
        {"id": "c1", "name": "Top", "type": "singles", "gender": "men", "category": {"id": "k1"}, "level": "grand_slam"},
        {"id": "c2", "name": "Child ok", "parent_id": "c1", "type": "singles", "gender": "men", "category": {"id": "k1"}},
        {"id": "c3", "name": "Child orphan", "parent_id": "MISSING", "type": "doubles", "gender": "men", "category": {"id": "k1"}},
    ]}
    p = profile_competitions(data)
    assert p["total"] == 3
    assert p["top_level_no_parent"] == 1
    assert p["with_parent_id"] == 2
    assert p["parent_id_resolves_in_dataset"] == 1
    assert p["parent_id_unresolved"] == 1
    assert p["parent_id_resolve_pct"] == 50.0
    assert p["level_present"] == 1          # level read from the competition object
    assert p["level_values"] == {"grand_slam": 1}


def test_profile_complexes_counts_empty_complexes():
    data = {"complexes": [
        {"id": "x1", "name": "A", "venues": [{"id": "v1", "country_code": "CHL", "timezone": "America/Santiago", "country_name": "Chile"}]},
        {"id": "x2", "name": "No venues"},
    ]}
    p = profile_complexes(data)
    assert p["complexes_with_venues"] == 1
    assert p["complexes_without_venues"] == 1
    assert p["venues"] == 1


def test_profile_rankings_ties_and_movement():
    data = {"rankings": [{"name": "ATP", "year": 2026, "week": 39, "gender": "men", "competitor_rankings": [
        {"rank": 1, "movement": 0, "points": 100, "competitions_played": 10, "competitor": {"id": "a"}},
        {"rank": 1, "movement": 2, "points": 100, "competitions_played": 12, "competitor": {"id": "b"}},
        {"rank": 3, "movement": 0, "points": 50, "competitions_played": 8, "competitor": {"id": "c"}},
    ]}]}
    p = profile_rankings(data)
    assert p["ranking_rows"] == 3
    assert p["rows_sharing_a_rank_with_another_row"] == 2
    assert p["movement_zero_pct"] == 66.67
    assert p["snapshots"][0]["competitors"] == 3


def test_profiles_handle_empty_payloads():
    assert profile_competitions({})["total"] == 0
    assert profile_complexes({})["venues"] == 0
    assert profile_rankings({})["ranking_rows"] == 0
