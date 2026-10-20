-- ============================================================
-- One-time upgrade for a database created with the FIRST version of schema.sql.
-- Run in MySQL Workbench with tennis_analytics selected.
-- "Duplicate key name" errors mean that index already exists - safe to ignore.
-- (ETL_Run_Log and the views are created automatically by `python main.py`.)
-- ============================================================

-- Needed for weekly upserts (skip if you already ran it)
ALTER TABLE Competitor_Rankings
    ADD UNIQUE KEY uq_competitor_week (competitor_id, ranking_year, ranking_week, ranking_gender);

-- Indexes that match how the app and queries actually filter
CREATE INDEX idx_venues_country_name ON Venues(country_name);
CREATE INDEX idx_competitors_country ON Competitors(country);
CREATE INDEX idx_rankings_snapshot ON Competitor_Rankings(ranking_year, ranking_week);
