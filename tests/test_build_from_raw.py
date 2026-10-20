"""The hosting file can be built from data/raw/*.json alone: no MySQL, no API key, no download."""
import json
import os
import sqlite3
import subprocess
import sys

import pytest
from streamlit.testing.v1 import AppTest

from database.build_snapshot_from_raw import build_snapshot
from test_app_smoke import APP
from test_sqlite_backend import use_snapshot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def person(pid, name, country="Spain", code="ESP"):
    return {"id": pid, "name": name, "country": country, "country_code": code, "abbreviation": name[:3].upper()}


def snapshot_json(week, rows):
    """rows: [(rank, points, competitor)]"""
    return {"rankings": [{"name": "ATP", "year": 2026, "week": week, "gender": "men", "competitor_rankings": [
        {"rank": r, "movement": 0, "points": p, "competitions_played": 10, "competitor": c} for r, p, c in rows]}]}


A, B, C = person("a", "Alpha, A", "Finland", "FIN"), person("b", "Bravo, B"), person("c", "Charlie, C")


@pytest.fixture()
def raw_dir(tmp_path):
    d = tmp_path / "raw"
    (d / "archive").mkdir(parents=True)
    comps = {"competitions": [
        {"id": "c1", "name": "Wimbledon Men Singles", "parent_id": "p1", "type": "singles", "gender": "men",
         "category": {"id": "k1", "name": "ATP"}, "level": "grand_slam"},
        {"id": "c2", "name": "ITF Men Somewhere", "type": "doubles", "gender": "men", "category": {"id": "k2", "name": "ITF Men"}},
    ]}
    cx = {"complexes": [
        {"id": "x1", "name": "Nacional", "venues": [{"id": "v1", "name": "Cancha Central", "city_name": "Santiago",
                                                     "country_name": "Chile", "country_code": "CHL", "timezone": "America/Santiago"}]},
        {"id": "x2", "name": "Empty complex"}]}
    week39 = snapshot_json(39, [(1, 1000, A), (2, 900, B)])
    week42 = snapshot_json(42, [(1, 1100, B), (2, 1000, A), (3, 800, C)])
    (d / "competitions.json").write_text(json.dumps(comps))
    (d / "complexes.json").write_text(json.dumps(cx))
    (d / "archive" / "doubles_rankings_20261001T000000.json").write_text(json.dumps(week39))
    (d / "archive" / "doubles_rankings_20261015T000000.json").write_text(json.dumps(week42))   # same as latest
    (d / "doubles_rankings.json").write_text(json.dumps(week42))
    return str(d)


def test_builds_every_table_dedupes_and_keeps_both_weeks(raw_dir, tmp_path):
    out = str(tmp_path / "tennis.db")
    counts = build_snapshot(raw_dir, out)
    assert counts["Categories"] == 2
    assert counts["Competitions"] == 2
    assert counts["Complexes"] == 2 and counts["Venues"] == 1
    assert counts["Competitors"] == 3
    assert counts["Competitor_Rankings"] == 5          # week 39 (2) + week 42 (3); the archived copy of week 42 is not doubled
    assert counts["ETL_Run_Log"] == 0

    conn = sqlite3.connect(out)
    assert conn.execute("SELECT category_level FROM Competitions WHERE competition_id='c1'").fetchone()[0] == "grand_slam"
    assert conn.execute("SELECT category_level FROM Competitions WHERE competition_id='c2'").fetchone()[0] is None
    ids = [r[0] for r in conn.execute("SELECT rank_id FROM Competitor_Rankings ORDER BY rank_id")]
    assert ids == [1, 2, 3, 4, 5]
    # the rank-history view sees both weeks: Alpha went from rank 1 (week 39) to rank 2 (week 42)
    prev, now = conn.execute("SELECT prev_rank, `rank` FROM v_rank_history WHERE name='Alpha, A' AND ranking_week=42").fetchone()
    assert (prev, now) == (1, 2)


def test_needs_no_api_key_and_no_mysql_driver(raw_dir, tmp_path):
    out = str(tmp_path / "tennis.db")
    code = ("import sys; sys.modules['mysql'] = None; sys.modules['mysql.connector'] = None\n"
            f"from database.build_snapshot_from_raw import build_snapshot\nprint(build_snapshot({raw_dir!r}, {out!r}))")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SPORTRADAR_", "DB_"))}
    env["PYTHONPATH"] = ROOT
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert os.path.exists(out)


def test_critical_data_problem_stops_the_build_and_leaves_no_file(raw_dir, tmp_path):
    path = os.path.join(raw_dir, "doubles_rankings.json")
    bad = json.load(open(path))
    bad["rankings"][0]["competitor_rankings"][0]["points"] = -5
    json.dump(bad, open(path, "w"))
    os.remove(os.path.join(raw_dir, "archive", "doubles_rankings_20261015T000000.json"))
    out = str(tmp_path / "tennis.db")
    with pytest.raises(ValueError, match="Critical"):
        build_snapshot(raw_dir, out)
    assert not os.path.exists(out)


def test_missing_raw_file_gives_a_clear_error(raw_dir, tmp_path):
    os.remove(os.path.join(raw_dir, "complexes.json"))
    with pytest.raises(FileNotFoundError, match="complexes.json"):
        build_snapshot(raw_dir, str(tmp_path / "tennis.db"))


def test_the_real_app_shows_rank_history_from_a_raw_built_snapshot(monkeypatch, raw_dir, tmp_path):
    out = str(tmp_path / "tennis.db")
    build_snapshot(raw_dir, out)
    use_snapshot(monkeypatch, out)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.radio[0].set_value("Rankings").run()
    assert not at.exception and not [e.value for e in at.error]
    assert any("Places gained" in d.value.columns for d in at.dataframe)       # risers/fallers appear with 2 weeks


def test_duplicate_competition_ids_stop_the_build_just_like_the_pipeline(raw_dir, tmp_path):
    path = os.path.join(raw_dir, "competitions.json")
    data = json.load(open(path))
    data["competitions"].append(dict(data["competitions"][0]))          # same id twice
    json.dump(data, open(path, "w"))
    out = str(tmp_path / "tennis.db")
    with pytest.raises(ValueError, match="duplicate_ids"):
        build_snapshot(raw_dir, out)
    assert not os.path.exists(out)
