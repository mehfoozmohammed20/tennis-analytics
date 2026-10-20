"""
Builds the hosting file data/tennis.db straight from the raw JSON files in data/raw/.
NO MySQL and NO API key are needed, and nothing is downloaded.

    python database/build_snapshot_from_raw.py

It uses the same transform and validation code as the pipeline (main.py), so the numbers match.
Ranking history: every weekly ranking file found in data/raw/archive/ is included, plus the latest one.
(Weeks that were only ever stored in MySQL and never saved as raw JSON are not available here.
To keep those, use `python database/export_to_sqlite.py` instead.)
"""
import glob
import json
import os
import sys

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault("SPORTRADAR_API_KEY", "offline-build-no-api-call")  # etl modules import api.config; this script never calls the API

from database.export_to_sqlite import DEFAULT_OUT, export_tables  # noqa: E402
from etl.transform import run_transformation  # noqa: E402
from etl.validate import is_clean, validate_dataset  # noqa: E402

RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")

COLUMNS = {
    "Categories": ["category_id", "category_name"],
    "Competitions": ["competition_id", "competition_name", "parent_id", "type", "gender", "category_id", "category_level"],
    "Complexes": ["complex_id", "complex_name"],
    "Venues": ["venue_id", "venue_name", "city_name", "country_name", "country_code", "timezone", "complex_id"],
    "Competitors": ["competitor_id", "name", "country", "country_code", "abbreviation"],
    "Competitor_Rankings": ["rank_id", "rank", "movement", "points", "competitions_played",
                            "ranking_year", "ranking_week", "ranking_gender", "competitor_id"],
    "ETL_Run_Log": ["run_id", "run_at", "status", "details"],
}
# a row is identified by these columns (the database upserts on them, so the last copy wins)
KEYS = {
    "Categories": ["category_id"], "Competitions": ["competition_id"], "Complexes": ["complex_id"],
    "Venues": ["venue_id"], "Competitors": ["competitor_id"],
    "Competitor_Rankings": ["competitor_id", "ranking_year", "ranking_week", "ranking_gender"],
}


def _load(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Raw file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _ranking_files(raw_dir: str) -> list:
    """Oldest first: archived weekly files, then the latest file."""
    archived = sorted(glob.glob(os.path.join(raw_dir, "archive", "doubles_rankings_*.json")))
    latest = os.path.join(raw_dir, "doubles_rankings.json")
    return archived + ([latest] if os.path.exists(latest) else [])


def build_tables(raw_dir: str = RAW_DIR) -> tuple:
    """Returns ({table: DataFrame}, report_text_lines). Raises if the raw files are missing or critically invalid."""
    competitions = _load(os.path.join(raw_dir, "competitions.json"))
    complexes = _load(os.path.join(raw_dir, "complexes.json"))
    files = _ranking_files(raw_dir)
    if not files:
        raise FileNotFoundError(f"No ranking file found in {raw_dir} (expected doubles_rankings.json)")

    snapshots = []
    for path in files:
        snapshots.extend(_load(path).get("rankings", []) or [])

    transformed = run_transformation({
        "competitions": competitions, "complexes": complexes, "doubles_rankings": {"rankings": snapshots},
    })

    report = validate_dataset(transformed)
    if not is_clean(report):
        bad = {t: c["_severity"]["critical_keys"] for t, c in report.items() if c["_severity"]["has_critical_issues"]}
        raise ValueError(f"Critical data problems, snapshot not built: {bad}")

    tables = {}
    for name, key in (("Categories", "categories"), ("Competitions", "competitions"), ("Complexes", "complexes"),
                      ("Venues", "venues"), ("Competitors", "competitors"), ("Competitor_Rankings", "rankings")):
        df = pd.DataFrame(transformed[key])
        df = df.drop_duplicates(subset=KEYS[name], keep="last").reset_index(drop=True)
        if name == "Competitor_Rankings":
            df.insert(0, "rank_id", range(1, len(df) + 1))
        tables[name] = df[COLUMNS[name]]
    tables["ETL_Run_Log"] = pd.DataFrame(columns=COLUMNS["ETL_Run_Log"])   # no pipeline runs are recorded for an offline build

    weeks = tables["Competitor_Rankings"].groupby(["ranking_year", "ranking_week", "ranking_gender"]).size()
    lines = [f"  ranking week {y}-W{w} ({g}): {n:,} competitors" for (y, w, g), n in weeks.items()]
    return tables, lines


def build_snapshot(raw_dir: str = RAW_DIR, out_path: str = DEFAULT_OUT) -> dict:
    tables, _ = build_tables(raw_dir)
    return export_tables(lambda name: tables.get(name), out_path)


def main():
    tables, week_lines = build_tables()
    counts = export_tables(lambda name: tables.get(name), DEFAULT_OUT)
    print(f"Created {DEFAULT_OUT} ({os.path.getsize(DEFAULT_OUT) / 1024:.0f} KB) from {RAW_DIR}\n")
    for table, n in counts.items():
        print(f"  {table:22} {n:,} rows")
    print("\nRanking weeks included:")
    print("\n".join(week_lines))
    if len(week_lines) < 4:      # men + women = 2 lists per week
        print("\nNote: only one ranking week is included, so the rank-history chart and the risers/fallers table "
              "will show 'no history yet'. Weeks stored only in MySQL can be added with "
              "`python database/export_to_sqlite.py` instead.")
    print("\nNext: commit data/tennis.db to GitHub, then deploy. See HOSTING.md.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"Could not build the snapshot: {e}")
