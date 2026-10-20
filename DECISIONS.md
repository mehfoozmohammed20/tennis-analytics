# Decisions Log

Non-obvious decisions, why they were made, and corrections made along the way.

## Schema
**`category_level`** — the API returns `level` (e.g. `grand_slam`, `atp_250`) on the competition object, next to `category`. Not in the brief, kept because it is a free analytical signal.
*Correction:* the first version of `transform.py` read `category.level`, which does not exist, so the column was NULL for every row. Found during a review of the code against the raw sample; fixed to read `level` (with a fallback), with a test. Re-run `python main.py` to populate it.

**`ranking_year / ranking_week / ranking_gender`** on Competitor_Rankings — rankings arrive as a weekly snapshot object wrapping the competitor list. Denormalised onto each row instead of a separate snapshot table: simpler at this scale.

**`UNIQUE (competitor_id, ranking_year, ranking_week, ranking_gender)`** — enables an upsert per competitor per week, so repeated weekly runs build history.

**`Competitions.parent_id` is not enforced as a foreign key on load.** Measured on the first load: 6,077 of 6,680 competitions have a `parent_id` that matches no `competition_id` in the same response. In the first rows of the response, parents such as `sr:competition:2553` (parent of the Wimbledon sub-events) never appear as their own row. The *reason* is **to be verified** — an earlier version of this log stated a cause as fact; that was an inference. `analysis_queries.sql` (A6) and the Data Quality page show how to check it.

**Extra indexes** on `Venues(country_name)`, `Competitors(country)` and `Competitor_Rankings(ranking_year, ranking_week)` — they match how queries and the app actually filter. Verify with `analysis/explain_queries.sql`.

**`rank` is backticked everywhere** — RANK is reserved in MySQL 8.0.2+ and caused a syntax error on `CREATE TABLE`.

## ETL
**Profile before transform** (`etl/profile.py`) — facts about the raw data (parent_id coverage, level coverage, ties, outliers) are measured and stored in the quality report instead of assumed.

**Rankings upsert instead of truncate-and-reload** — wiping history on every run would make trend analysis impossible. One run still contains one week; no synthetic history is created.

**Validation severity** — critical issues (duplicate keys, negative points/rank, missing names) stop the load; informational flags (`orphan_parent_refs`) are reported but do not.

**Raw JSON archive** — every run keeps an immutable timestamped copy in `data/raw/archive/` (git-ignored).

**Reconciliation and run log** — counts are compared API → transform → database, and each run is written to `ETL_Run_Log` (success or failure).

**Analytical views applied by the pipeline** — window-function logic lives in SQL (`database/views.sql`); a view failure is logged and does not undo a successful load.

## Dashboard
**Computed insights** — captions are built from the numbers on screen (shares, concentration, minimum-sample averages), not from templates about the top row.

**Latest-snapshot filtering** — because rankings now accumulate, ranking queries are limited to the latest (year, week).

**Minimum sample size on country averages** (adjustable slider) so a country with 1–2 players cannot top the list.

## Scope
**No predictive model** — outside the brief and not supportable with one weekly snapshot.

**No per-capita metrics** — would need external population data; points-per-competition is used as a denominator-based metric from data already in the pipeline.

## Known gaps
- No automated tests against a real MySQL database; views/queries were tested on SQLite and by running the pipeline.
- Only one weekly snapshot exists until the pipeline is run again.
