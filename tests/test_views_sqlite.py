"""
Runs database/views.sql against an in-memory SQLite copy of the schema to verify the
window-function logic (DENSE_RANK, SUM OVER, LAG). SQLite is only a stand-in for
MySQL 8 here: 'CREATE OR REPLACE VIEW' is rewritten to 'CREATE VIEW'.
"""
import os
import sqlite3
import pytest

from etl.load import split_sql_statements, VIEWS_PATH


@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE Categories (category_id TEXT PRIMARY KEY, category_name TEXT);
        CREATE TABLE Competitions (competition_id TEXT PRIMARY KEY, competition_name TEXT, parent_id TEXT,
            type TEXT, gender TEXT, category_id TEXT, category_level TEXT);
        CREATE TABLE Competitors (competitor_id TEXT PRIMARY KEY, name TEXT, country TEXT, country_code TEXT, abbreviation TEXT);
        CREATE TABLE Competitor_Rankings (rank_id INTEGER PRIMARY KEY AUTOINCREMENT, `rank` INT, movement INT, points INT,
            competitions_played INT, ranking_year INT, ranking_week INT, ranking_gender TEXT, competitor_id TEXT);
    """)
    conn.executemany("INSERT INTO Competitors VALUES (?,?,?,?,?)", [
        ("A", "Alpha", "Finland", "FIN", "ALP"), ("B", "Bravo", "Spain", "ESP", "BRA"),
        ("C", "Charlie", "Spain", "ESP", "CHA"), ("D", "Delta", "Italy", "ITA", "DEL")])
    # week 39: points 1000 / 800 / 800 (tie) / 500   -> total 3100
    conn.executemany("INSERT INTO Competitor_Rankings (`rank`,movement,points,competitions_played,ranking_year,ranking_week,ranking_gender,competitor_id) VALUES (?,?,?,?,?,?,?,?)", [
        (1, 0, 1000, 20, 2026, 39, "men", "A"), (2, 0, 800, 18, 2026, 39, "men", "B"),
        (2, 0, 800, 22, 2026, 39, "men", "C"), (4, 0, 500, 15, 2026, 39, "men", "D"),
        # week 40: Alpha drops to rank 2
        (1, 1, 950, 21, 2026, 40, "men", "B"), (2, -1, 900, 21, 2026, 40, "men", "A")])
    conn.execute("INSERT INTO Categories VALUES ('k1','ATP')")
    conn.executemany("INSERT INTO Competitions VALUES (?,?,?,?,?,?,?)", [
        ("c1", "Wimbledon Men Singles", None, "singles", "men", "k1", "grand_slam"),
        ("c2", "Wimbledon Men Doubles", None, "doubles", "men", "k1", "grand_slam")])
    with open(VIEWS_PATH, encoding="utf-8") as f:
        for stmt in split_sql_statements(f.read()):
            conn.execute(stmt.replace("CREATE OR REPLACE VIEW", "CREATE VIEW"))
    return conn


def test_leaderboard_dense_rank_handles_ties(db):
    rows = db.execute("SELECT name, points_dense_rank FROM v_ranking_leaderboard "
                      "WHERE ranking_week = 39 ORDER BY name").fetchall()
    assert dict(rows) == {"Alpha": 1, "Bravo": 2, "Charlie": 2, "Delta": 3}


def test_leaderboard_share_and_cumulative(db):
    share, cum = db.execute("SELECT pct_of_total_points, cumulative_pct_of_points FROM v_ranking_leaderboard "
                            "WHERE ranking_week = 39 AND name = 'Alpha'").fetchone()
    assert share == 32.26                      # 1000 / 3100
    last = db.execute("SELECT MAX(cumulative_pct_of_points) FROM v_ranking_leaderboard WHERE ranking_week = 39").fetchone()[0]
    assert last == 100.0


def test_points_concentration_top10_share(db):
    share = db.execute("SELECT top10_share_pct FROM v_points_concentration WHERE ranking_week = 39").fetchone()[0]
    assert share == 100.0                      # only 4 competitors, all inside the top 10


def test_rank_history_lag(db):
    prev_rank, rank = db.execute("SELECT prev_rank, `rank` FROM v_rank_history "
                                 "WHERE name = 'Alpha' AND ranking_week = 40").fetchone()
    assert (prev_rank, rank) == (1, 2)
    first = db.execute("SELECT prev_rank FROM v_rank_history WHERE name = 'Alpha' AND ranking_week = 39").fetchone()[0]
    assert first is None


def test_competition_summary(db):
    rows = db.execute("SELECT type, category_level, competition_count FROM v_competition_summary ORDER BY type").fetchall()
    assert rows == [("doubles", "grand_slam", 1), ("singles", "grand_slam", 1)]
