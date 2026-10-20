"""
Copies the MySQL database into ONE file, data/tennis.db (SQLite), so the dashboard can be hosted
without a database server. Run it on your own machine, where MySQL is running:

    python database/export_to_sqlite.py

Then commit data/tennis.db to GitHub. Re-run it (and commit again) whenever you reload the data
with `python main.py`.
"""
import os
import sqlite3
import sys

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

VIEWS_PATH = os.path.join(PROJECT_ROOT, "database", "views.sql")
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "data", "tennis.db")
TABLES = ["Categories", "Competitions", "Complexes", "Venues", "Competitors", "Competitor_Rankings", "ETL_Run_Log"]
REQUIRED = TABLES[:-1]          # ETL_Run_Log is optional (older databases do not have it)
VIEWS = ["v_ranking_leaderboard", "v_points_concentration", "v_rank_history", "v_competition_summary"]


def split_sql_statements(sql_text: str) -> list:
    """Drops full-line '--' comments, then splits on ';' into statements."""
    lines = [ln for ln in sql_text.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def export_tables(read_table, out_path: str = DEFAULT_OUT, views_path: str = VIEWS_PATH) -> dict:
    """
    read_table(name) -> DataFrame, or None when the table does not exist.
    Builds the file next to the target and swaps it in only when everything worked,
    so a failed export never destroys the previous snapshot.
    Returns {table: row_count} (None for a missing optional table).
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp_path = out_path + ".tmp"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    counts = {}
    conn = sqlite3.connect(tmp_path)
    try:
        for table in TABLES:
            df = read_table(table)
            if df is None:
                if table in REQUIRED:
                    raise RuntimeError(f"Required table {table} was not found in the source database.")
                counts[table] = None
                continue
            df.to_sql(table, conn, index=False, if_exists="replace")
            written = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if written != len(df):
                raise RuntimeError(f"{table}: wrote {written} rows but read {len(df)}")
            counts[table] = written

        with open(views_path, "r", encoding="utf-8") as f:
            for stmt in split_sql_statements(f.read()):
                conn.execute(stmt.replace("CREATE OR REPLACE VIEW", "CREATE VIEW"))
        for view in VIEWS:                      # prove every view actually runs
            conn.execute(f"SELECT COUNT(*) FROM {view}").fetchone()
        conn.commit()
    except Exception:
        conn.close()
        os.remove(tmp_path)
        raise
    conn.close()
    os.replace(tmp_path, out_path)
    return counts


def read_from_mysql(table: str):
    from database.connection import get_mysql_connection
    conn = get_mysql_connection()
    try:
        return pd.read_sql(f"SELECT * FROM {table}", conn)
    except Exception:
        return None
    finally:
        conn.close()


def main():
    print("Reading from MySQL ...")
    counts = export_tables(read_from_mysql)
    print(f"\nCreated {DEFAULT_OUT} ({os.path.getsize(DEFAULT_OUT) / 1024:.0f} KB)\n")
    for table, n in counts.items():
        print(f"  {table:22} {'(not in database, skipped)' if n is None else f'{n:,} rows'}")
    print("\nNext: commit data/tennis.db to GitHub, then deploy. See HOSTING.md.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"Export failed: {e}\nIs MySQL running, and are DB_USER / DB_PASSWORD / DB_NAME in your .env correct?")
