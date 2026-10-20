-- ============================================================
-- SportRadar Tennis Analytics — Database Schema
-- Engine: MySQL (adjust AUTO_INCREMENT/CHAR syntax if PostgreSQL)
-- ============================================================

-- 1. Categories
CREATE TABLE Categories (
    category_id     VARCHAR(50)  PRIMARY KEY,
    category_name   VARCHAR(100) NOT NULL
);

-- 2. Competitions (self-referencing hierarchy)
CREATE TABLE Competitions (
    competition_id      VARCHAR(50)  PRIMARY KEY,
    competition_name    VARCHAR(150) NOT NULL,
    parent_id            VARCHAR(50)  NULL,
    type                 VARCHAR(20)  NOT NULL,   -- singles/doubles/mixed_doubles
    gender               VARCHAR(10)  NOT NULL,   -- men/women/mixed
    category_id          VARCHAR(50)  NOT NULL,
    category_level       VARCHAR(30)  NULL,       -- API field `level` (e.g. grand_slam, atp_250); sits next to `category`, not inside it
    FOREIGN KEY (category_id) REFERENCES Categories(category_id),
    FOREIGN KEY (parent_id) REFERENCES Competitions(competition_id)
);

-- 3. Complexes
CREATE TABLE Complexes (
    complex_id      VARCHAR(50)  PRIMARY KEY,
    complex_name    VARCHAR(100) NOT NULL
);

-- 4. Venues
CREATE TABLE Venues (
    venue_id        VARCHAR(50)  PRIMARY KEY,
    venue_name      VARCHAR(100) NOT NULL,
    city_name       VARCHAR(100) NOT NULL,
    country_name    VARCHAR(100) NOT NULL,
    country_code    CHAR(3)      NOT NULL,
    timezone        VARCHAR(100) NOT NULL,
    complex_id      VARCHAR(50)  NULL,   -- nullable: some complexes have no venues in API, but a venue always ties back if present
    FOREIGN KEY (complex_id) REFERENCES Complexes(complex_id)
);

-- 5. Competitors
CREATE TABLE Competitors (
    competitor_id    VARCHAR(50)  PRIMARY KEY,
    name             VARCHAR(100) NOT NULL,
    country          VARCHAR(100) NOT NULL,
    country_code     CHAR(3)      NOT NULL,
    abbreviation     VARCHAR(10)  NOT NULL
);

-- 6. Competitor_Rankings
-- Note: actual API nests rankings under a snapshot (type_id/year/week/gender)
-- rather than flat rows as originally specced. Snapshot fields added here
-- rather than a separate meta table, to keep schema simple for scope/timeline.
CREATE TABLE Competitor_Rankings (
    rank_id              INT AUTO_INCREMENT PRIMARY KEY,
    `rank`               INT NOT NULL,
    movement             INT NOT NULL,
    points                INT NOT NULL,
    competitions_played  INT NOT NULL,
    ranking_year          INT NOT NULL,   -- from API snapshot, not in original spec
    ranking_week          INT NOT NULL,   -- from API snapshot, not in original spec
    ranking_gender         VARCHAR(10) NOT NULL, -- from API snapshot, not in original spec
    competitor_id          VARCHAR(50) NOT NULL,
    FOREIGN KEY (competitor_id) REFERENCES Competitors(competitor_id),
    UNIQUE KEY uq_competitor_week (competitor_id, ranking_year, ranking_week, ranking_gender)
);

-- Indexes for common query patterns
CREATE INDEX idx_competitions_category ON Competitions(category_id);
CREATE INDEX idx_competitions_parent ON Competitions(parent_id);
CREATE INDEX idx_venues_complex ON Venues(complex_id);
CREATE INDEX idx_venues_country ON Venues(country_code);
CREATE INDEX idx_rankings_competitor ON Competitor_Rankings(competitor_id);
CREATE INDEX idx_rankings_rank ON Competitor_Rankings(`rank`);
CREATE INDEX idx_venues_country_name ON Venues(country_name);
CREATE INDEX idx_competitors_country ON Competitors(country);
CREATE INDEX idx_rankings_snapshot ON Competitor_Rankings(ranking_year, ranking_week);

-- Audit table: one row per pipeline run (also created automatically by main.py)
CREATE TABLE IF NOT EXISTS ETL_Run_Log (
    run_id   INT AUTO_INCREMENT PRIMARY KEY,
    run_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    status   VARCHAR(20) NOT NULL,
    details  TEXT
);

-- Analytical views live in database/views.sql (applied automatically by main.py)
