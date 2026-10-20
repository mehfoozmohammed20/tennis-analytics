# Game Analytics: Unlocking Tennis Data with SportRadar API

An end-to-end analytics project: SportRadar Tennis API → Python ETL → MySQL → SQL analysis → Streamlit dashboard.

## Problem
Tennis competition hierarchies, venue/complex data and doubles rankings sit in three separate API responses that are hard to browse. This project loads them into one validated relational database and exposes them through SQL queries and an interactive dashboard.

## Architecture
```
SportRadar API
   ↓  api/ + etl/extract.py        raw JSON (latest + immutable timestamped archive)
   ↓  etl/profile.py               measures the raw data (null rates, uniques, coverage, outliers)
   ↓  etl/transform.py             nested JSON → flat relational rows
   ↓  etl/validate.py              critical vs informational checks (critical stops the load)
   ↓  etl/load.py                  MySQL upserts in one transaction
   ↓  views.sql / reconcile.py     window-function views, row-count reconciliation, run log
   ↓  analysis/*.sql               20 mandatory + additional + window-function queries
   ↓  app/streamlit_app.py         6-page dashboard
```

## Tech
Python 3.11+, MySQL 8+, Streamlit, pandas, requests, python-dotenv, pytest.

## Data model
6 tables (Categories, Competitions, Complexes, Venues, Competitors, Competitor_Rankings) plus an `ETL_Run_Log` audit table and 4 views. Field-level definitions: [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md). DDL: [`database/schema.sql`](database/schema.sql).

Differences between the brief and the real API response (details in [`DECISIONS.md`](DECISIONS.md)):
- `category_level` added — the API returns a tournament `level` (e.g. `grand_slam`) on each competition, next to `category`.
- `ranking_year/week/gender` added — rankings arrive wrapped in a weekly snapshot object, not as flat rows.
- Some complexes have no venues; `parent_id` mostly does not resolve inside the competitions response (the foreign key is not enforced for that column; the cause is **to be verified**).

## Setup
1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env`; fill in your SportRadar key and MySQL credentials. Never commit `.env`.
3. In MySQL: `CREATE DATABASE tennis_analytics;` then run `database/schema.sql`.
   - Database created from an older version of the schema? Run `database/upgrade_existing_db.sql` once instead.
4. `python main.py` — runs the whole pipeline, creates the views, writes `data/quality_report.json`.
5. `streamlit run app/streamlit_app.py`

Run `python main.py` weekly to accumulate ranking history: rankings upsert per (competitor, year, week, gender) instead of being overwritten.

## Pipeline reliability
- API: timeouts, retries with backoff, HTTP 429 handling, clear errors on bad JSON.
- Transform: malformed records skipped with a logged warning; shared entities deduplicated.
- Validation: **critical** issues (duplicate keys, negative points/rank) stop the load; **informational** flags are reported only.
- Load: one transaction, rollback on any error, idempotent upserts.
- Proof: raw → transformed → database row counts reconciled; every run written to `ETL_Run_Log`. The results are written to `data/quality_report.json` after every run.

## SQL
- [`analysis/analysis_queries.sql`](analysis/analysis_queries.sql): the 20 required queries, additional queries (A1–A6), and window-function queries (W1–W4).
- [`database/views.sql`](database/views.sql): `v_ranking_leaderboard` (DENSE_RANK, running share), `v_points_concentration`, `v_rank_history` (LAG), `v_competition_summary`.
- [`analysis/explain_queries.sql`](analysis/explain_queries.sql): EXPLAIN statements to check index usage on your own data.

## Dashboard
Overview · Competition Explorer (category/type/level filters) · Venue Explorer · Rankings (histograms, minimum-sample country analysis, efficiency, concentration, rank movement) · Competitor Explorer · Limitations & Future Implementation. Insight captions are computed from the data shown. All queries are parameterized.

## Tests
`pytest tests/ -v` — 57 tests: profiling, transform, validation, reconciliation, the SQL views (run on a SQLite stand-in), pipeline orchestration, and a smoke test that renders every app page.
Not covered: live API calls, real MySQL execution (verify by running the pipeline), automated tests against a MySQL test database.

## Limitations
- One weekly ranking snapshot so far, so no trend analysis until more weeks are collected (the app shows risers/fallers automatically once two exist).
- No predictive model: out of scope and not supportable with one week of data.
- Venue counts are raw counts, not adjusted for country size.
- Views and queries were tested on SQLite; MySQL-specific behaviour is confirmed by running `python main.py` and `EXPLAIN` locally.

## Future work
Schedule the weekly run, add rank-movement charts once history exists, add a second data source for per-capita benchmarks, add MySQL integration tests.
