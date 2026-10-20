"""
Hosting without a database server: export MySQL -> data/tennis.db (SQLite), and run the real app on that file.
The 'source' database here is a SQLite stand-in for MySQL (same tables and sample rows as the other tests).
"""
import os
import sqlite3

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import database.connection as dbc
from database.export_to_sqlite import export_tables
from test_app_smoke import APP, PAGES, build_db


def source_reader(conn):
    def read(table):
        try:
            return pd.read_sql_query(f"SELECT * FROM {table}", conn)
        except Exception:
            return None
    return read


@pytest.fixture()
def snapshot(tmp_path):
    src = build_db(two_weeks=True)
    # one competitor whose points / competitions is NOT a whole number: 5000 / 7 = 714.29
    src.execute("INSERT INTO Competitors VALUES ('z','Zulu','Spain','ESP','ZUL')")
    src.execute("INSERT INTO Competitor_Rankings (`rank`,movement,points,competitions_played,ranking_year,ranking_week,"
                "ranking_gender,competitor_id) VALUES (9,0,5000,7,2026,40,'men','z')")
    out = str(tmp_path / "tennis.db")
    counts = export_tables(source_reader(src), out)
    return out, counts, src


def use_snapshot(monkeypatch, path):
    for var in ("DB_PASSWORD", "DB_BACKEND"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SQLITE_PATH", path)
    st.cache_data.clear()


# ---------- which backend is chosen ----------
def test_backend_rules(monkeypatch, tmp_path):
    snap = tmp_path / "tennis.db"
    snap.write_bytes(b"")
    monkeypatch.setenv("SQLITE_PATH", str(snap))
    monkeypatch.delenv("DB_BACKEND", raising=False)

    monkeypatch.delenv("DB_PASSWORD", raising=False)
    assert dbc.backend_name() == "sqlite"            # hosted: no password configured and a snapshot exists
    monkeypatch.setenv("DB_PASSWORD", "secret")
    assert dbc.backend_name() == "mysql"             # your machine: a password is configured
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    assert dbc.backend_name() == "sqlite"            # explicit choice wins
    monkeypatch.setenv("DB_BACKEND", "mysql")
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    assert dbc.backend_name() == "mysql"

    monkeypatch.delenv("DB_BACKEND", raising=False)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "missing.db"))
    assert dbc.backend_name() == "mysql"             # no snapshot file: fall back to MySQL (and its clear error message)


# ---------- export ----------
def test_export_copies_every_table_and_views_work(snapshot):
    out, counts, src = snapshot
    for table in ("Categories", "Competitions", "Complexes", "Venues", "Competitors", "Competitor_Rankings", "ETL_Run_Log"):
        assert counts[table] == src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn = sqlite3.connect(out)
    assert conn.execute("SELECT COUNT(*) FROM v_ranking_leaderboard").fetchone()[0] == counts["Competitor_Rankings"]
    assert conn.execute("SELECT COUNT(*) FROM v_rank_history WHERE prev_rank IS NOT NULL").fetchone()[0] > 0


def test_failed_export_keeps_the_previous_snapshot(snapshot):
    out, _, src = snapshot
    before = open(out, "rb").read()

    def broken(table):
        if table == "Venues":
            raise RuntimeError("MySQL went away")
        return source_reader(src)(table)

    with pytest.raises(RuntimeError):
        export_tables(broken, out)
    assert open(out, "rb").read() == before
    assert not os.path.exists(out + ".tmp")


def test_export_refuses_when_a_required_table_is_missing(snapshot, tmp_path):
    _, _, src = snapshot
    reader = source_reader(src)
    with pytest.raises(RuntimeError, match="Venues"):
        export_tables(lambda t: None if t == "Venues" else reader(t), str(tmp_path / "x.db"))


# ---------- the hosted app, for real ----------
def test_connection_is_read_only_and_translates_placeholders(snapshot, monkeypatch):
    out, _, _ = snapshot
    use_snapshot(monkeypatch, out)
    conn = dbc.get_connection()
    df = pd.read_sql("SELECT name FROM Competitors WHERE country = %s", conn, params=("Spain",))
    assert len(df) == 4
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("CREATE TABLE should_fail (a INT)")
    conn.close()


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_from_the_snapshot_with_no_database_server(monkeypatch, snapshot, page):
    out, _, _ = snapshot
    use_snapshot(monkeypatch, out)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]
    assert not [e.value for e in at.error], [e.value for e in at.error]
    assert any("saved snapshot" in c.value for c in at.sidebar.caption)


def test_efficiency_uses_decimal_division_on_sqlite(monkeypatch, snapshot):
    out, _, _ = snapshot
    use_snapshot(monkeypatch, out)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.radio[0].set_value("Rankings").run()
    table = next(d.value for d in at.dataframe if "points_per_competition" in d.value.columns)
    assert float(table["points_per_competition"].max()) == 714.3      # 5000 / 7, not the whole number 714
