"""
Smoke test: every Streamlit page renders without a Python exception.
Uses an in-memory SQLite stand-in for MySQL (same tables, the real views.sql, sample rows).
This checks the app's code paths, NOT MySQL-specific SQL behaviour.
"""
import json
import os
import shutil
import sqlite3

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import main as pipeline
from etl.load import split_sql_statements, VIEWS_PATH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app", "streamlit_app.py")
REPORT = os.path.join(ROOT, "data", "quality_report.json")

PAGES = ["Overview", "Competition Explorer", "Venue Explorer", "Rankings",
         "Competitor Explorer", "SQL Analysis", "Limitations & Future Implementation"]


def build_db(two_weeks: bool) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript("""
        CREATE TABLE Categories (category_id TEXT PRIMARY KEY, category_name TEXT);
        CREATE TABLE Competitions (competition_id TEXT PRIMARY KEY, competition_name TEXT, parent_id TEXT,
            type TEXT, gender TEXT, category_id TEXT, category_level TEXT);
        CREATE TABLE Complexes (complex_id TEXT PRIMARY KEY, complex_name TEXT);
        CREATE TABLE Venues (venue_id TEXT PRIMARY KEY, venue_name TEXT, city_name TEXT, country_name TEXT,
            country_code TEXT, timezone TEXT, complex_id TEXT);
        CREATE TABLE Competitors (competitor_id TEXT PRIMARY KEY, name TEXT, country TEXT, country_code TEXT, abbreviation TEXT);
        CREATE TABLE Competitor_Rankings (rank_id INTEGER PRIMARY KEY AUTOINCREMENT, `rank` INT, movement INT, points INT,
            competitions_played INT, ranking_year INT, ranking_week INT, ranking_gender TEXT, competitor_id TEXT);
        CREATE TABLE ETL_Run_Log (run_id INTEGER PRIMARY KEY AUTOINCREMENT, run_at TEXT, status TEXT, details TEXT);
    """)
    conn.execute("INSERT INTO Categories VALUES ('k1','ATP'),('k2','WTA')")
    conn.executemany("INSERT INTO Competitions VALUES (?,?,?,?,?,?,?)", [
        ("c1", "Wimbledon Men Singles", "p1", "singles", "men", "k1", "grand_slam"),
        ("c2", "Wimbledon Men Doubles", "p1", "doubles", "men", "k1", "grand_slam"),
        ("c3", "Hopman Cup", None, "mixed", "mixed", "k2", None)])
    conn.execute("INSERT INTO Complexes VALUES ('x1','Nacional'),('x2','Other')")
    conn.executemany("INSERT INTO Venues VALUES (?,?,?,?,?,?,?)", [
        ("v1", "Cancha Central", "Santiago", "Chile", "CHL", "America/Santiago", "x1"),
        ("v2", "Court 2", "Santiago", "Chile", "CHL", "America/Santiago", "x1"),
        ("v3", "Court A", "Madrid", "Spain", "ESP", "Europe/Madrid", "x2")])
    people = [("a", "Alpha", "Finland", "FIN", "ALP"), ("b", "Bravo", "Spain", "ESP", "BRA"),
              ("c", "Charlie", "Spain", "ESP", "CHA"), ("d", "Delta", "Spain", "ESP", "DEL"),
              ("e", "Echo", "Italy", "ITA", "ECH")]
    conn.executemany("INSERT INTO Competitors VALUES (?,?,?,?,?)", people)
    cols = "(`rank`,movement,points,competitions_played,ranking_year,ranking_week,ranking_gender,competitor_id)"
    rows = [(i + 1, 0, 1000 - 100 * i, 20 - i, 2026, 39, "men", p[0]) for i, p in enumerate(people)]
    if two_weeks:
        rows += [(i + 1, 1, 1050 - 100 * i, 21 - i, 2026, 40, "men", p[0]) for i, p in enumerate(reversed(people))]
    conn.executemany(f"INSERT INTO Competitor_Rankings {cols} VALUES (?,?,?,?,?,?,?,?)", rows)
    with open(VIEWS_PATH, encoding="utf-8") as f:
        for stmt in split_sql_statements(f.read()):
            conn.execute(stmt.replace("CREATE OR REPLACE VIEW", "CREATE VIEW"))
    return conn


class _Conn:
    def __init__(self, raw):
        self.raw = raw

    def close(self):
        pass


@pytest.fixture()
def quality_report(monkeypatch):
    """Generate a real report with the pipeline's own code, then restore whatever was there."""
    backup = REPORT + ".bak"
    existed = os.path.exists(REPORT)
    if existed:
        shutil.copy(REPORT, backup)
    raw = {
        "competitions": {"competitions": [{"id": "c1", "name": "A", "parent_id": "zz", "type": "singles",
                                           "gender": "men", "category": {"id": "k1", "name": "ATP"}, "level": "atp_250"}]},
        "complexes": {"complexes": [{"id": "x1", "name": "N", "venues": [
            {"id": "v1", "name": "C", "city_name": "S", "country_name": "Chile", "country_code": "CHL", "timezone": "America/Santiago"}]}]},
        "doubles_rankings": {"rankings": [{"name": "ATP", "year": 2026, "week": 39, "gender": "men", "competitor_rankings": [
            {"rank": 1, "movement": 0, "points": 10, "competitions_played": 3,
             "competitor": {"id": "a", "name": "Alpha", "country": "Finland", "country_code": "FIN", "abbreviation": "ALP"}}]}]},
    }
    monkeypatch.setattr(pipeline, "run_extraction", lambda: raw)
    monkeypatch.setattr(pipeline, "run_load", lambda d: None)
    monkeypatch.setattr(pipeline, "apply_views", lambda: {"applied": 4, "failed": []})
    monkeypatch.setattr(pipeline, "run_db_reconciliation", lambda t: {"competitions": {
        "rows_this_run": 1, "unique_rows_this_run": 1, "duplicates_collapsed_by_upsert": 0, "in_database": 1, "ok": True},
        "rankings_duplicate_groups_in_db": {"count": 0, "ok": True}})
    monkeypatch.setattr(pipeline, "log_run", lambda s, d: None)
    monkeypatch.setattr(pipeline, "QUALITY_REPORT_PATH", REPORT)
    pipeline.main()
    yield
    if existed:
        shutil.move(backup, REPORT)
    elif os.path.exists(REPORT):
        os.remove(REPORT)


def run_page(monkeypatch, page, two_weeks):
    sqlite_conn = build_db(two_weeks)
    import database.connection as dbc
    monkeypatch.setattr(dbc, "get_connection", lambda: _Conn(sqlite_conn))
    monkeypatch.setattr(pd, "read_sql",
                        lambda sql, conn, params=None: pd.read_sql_query(sql.replace("%s", "?"), conn.raw, params=params))
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, f"landing page raised: {[e.value for e in at.exception]}"
    at.sidebar.radio[0].set_value(page).run()
    return at


@pytest.mark.parametrize("two_weeks", [False, True])
@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_exception(monkeypatch, quality_report, page, two_weeks):
    at = run_page(monkeypatch, page, two_weeks)
    assert not at.exception, f"{page} raised: {[e.value for e in at.exception]}"
    assert not [e.value for e in at.error if str(e.value).startswith("Database error")], \
        f"{page} hit a database error: {[e.value for e in at.error]}"


@pytest.mark.parametrize("page", ["Overview", "Competition Explorer", "Venue Explorer", "Rankings", "Competitor Explorer"])
def test_database_down_shows_one_clear_message(monkeypatch, page):
    import database.connection as dbc

    def refuse():
        raise Exception("1045 (28000): Access denied for user 'root'@'localhost' (using password: NO)")

    monkeypatch.setattr(dbc, "get_connection", refuse)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception
    errors = [e.value for e in at.error]
    assert len(errors) == 1 and "Cannot connect to MySQL" in errors[0]


def test_limitations_page_works_when_database_is_down_and_has_both_sections(monkeypatch):
    import database.connection as dbc
    monkeypatch.setattr(dbc, "get_connection", lambda: (_ for _ in ()).throw(Exception("down")))
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.radio[0].set_value("Limitations & Future Implementation").run()
    assert not at.exception
    headings = [m.value for m in at.markdown]
    assert any("Limitations of this project" in h for h in headings)
    assert any("Future implementation" in h for h in headings)


def test_sidebar_has_exactly_the_seven_pages():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert list(at.sidebar.radio[0].options) == [
        "Overview", "Competition Explorer", "Venue Explorer", "Rankings",
        "Competitor Explorer", "SQL Analysis", "Limitations & Future Implementation"]


def _chart_specs(at):
    def walk(node):
        for ch in getattr(node, "children", {}).values():
            yield ch
            yield from walk(ch)
    return [json.loads(el.proto.spec) for el in walk(at.main) if el.type == "vega_lite_chart"]


def _sort_of_category_axis(spec):
    enc = spec["encoding"]
    axis = enc["x"] if enc["x"].get("type") == "nominal" else enc["y"]
    return axis.get("sort", "(default)")


def test_rankings_histograms_keep_bin_order_and_ranked_bars_sort_by_value(monkeypatch, quality_report):
    at = run_page(monkeypatch, "Rankings", two_weeks=True)
    specs = {sp["encoding"]["x"].get("title"): sp for sp in _chart_specs(at)}
    assert _sort_of_category_axis(specs["Points range"]) is None                  # histogram: numeric order
    assert _sort_of_category_axis(specs["Competitions played (range)"]) is None
    assert _sort_of_category_axis(specs["Country"]) == "-y"                       # ranked: largest first


def test_venue_chart_is_horizontal_and_sorted_by_count(monkeypatch, quality_report):
    at = run_page(monkeypatch, "Venue Explorer", two_weeks=False)
    (spec,) = _chart_specs(at)
    assert spec["encoding"]["y"]["type"] == "nominal"        # countries on the vertical axis
    assert _sort_of_category_axis(spec) == "-x"              # sorted by the count on the horizontal axis


def test_every_chart_has_axis_titles(monkeypatch, quality_report):
    for page in ["Overview", "Competition Explorer", "Venue Explorer", "Rankings", "Competitor Explorer"]:
        at = run_page(monkeypatch, page, two_weeks=True)
        for spec in _chart_specs(at):
            assert spec["encoding"]["x"].get("title") and spec["encoding"]["y"].get("title"), page


def test_overview_shows_architecture_before_dataset_overview_and_live_design_table(monkeypatch):
    at = run_page(monkeypatch, "Overview", two_weeks=True)
    assert not at.exception
    # architecture diagram
    assert any("SportRadar API" in c.value and "Streamlit Dashboard" in c.value for c in at.code)
    # order on the page: Architecture heading comes before Dataset Overview
    subs = [h.value for h in at.subheader]
    assert subs.index("Architecture") < subs.index("Dataset Overview")
    # database design: real tables, row counts read from the database (test data: 3 competitions, 3 venues, 5 competitors)
    design = next(m.value for m in at.markdown if "| Table | Rows |" in m.value)
    assert "| **Competitions** | 3 |" in design
    assert "| **Venues** | 3 |" in design
    assert "| **Competitors** | 5 |" in design
    assert "| **ETL_Run_Log** | 0 |" in design
    assert "Tournaments" not in design          # no such table exists in this project


def test_sql_analysis_page_lists_all_twenty_queries_and_needs_no_database(monkeypatch):
    import database.connection as dbc
    monkeypatch.setattr(dbc, "get_connection", lambda: (_ for _ in ()).throw(Exception("down")))
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.radio[0].set_value("SQL Analysis").run()
    assert not at.exception
    text = "\n".join(m.value for m in at.markdown)
    for n in range(1, 21):
        assert f"| Q{n} |" in text, f"Q{n} missing"
    assert "Q21" not in text
    assert [h.value for h in at.subheader] == [
        "Competitions (Q1–Q7)", "Complexes and venues (Q8–Q14)", "Rankings and competitors (Q15–Q20)"]


def test_ranking_queries_use_only_the_latest_snapshot():
    """Rankings accumulate weekly, so Q15-Q18 must not mix or double count stored weeks."""
    import re
    sql_text = open(os.path.join(ROOT, "analysis", "analysis_queries.sql"), encoding="utf-8").read()

    def query(label):
        return re.search(rf"-- {label}:.*?;", sql_text, flags=re.S).group(0)

    conn = build_db(two_weeks=True)          # week 39 and week 40, 5 competitors each; Spain = 3 players
    q15 = conn.execute(query("Q15")).fetchall()
    assert len(q15) == 5 and {row[5] for row in q15} == {40}
    assert len(conn.execute(query("Q16")).fetchall()) == 5
    # Spain in week 40 only: 950 + 850 + 750 (summing both weeks would give 4950)
    assert conn.execute(query("Q18").replace("Croatia", "Spain")).fetchall() == [("Spain", 2550)]
