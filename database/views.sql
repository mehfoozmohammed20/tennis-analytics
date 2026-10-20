-- ============================================================
-- Analytical views (MySQL 8+, uses window functions)
-- Applied automatically by `python main.py` (etl/load.py: apply_views)
-- Keep this file free of semicolons inside comments - it is split on them.
-- ============================================================

-- V1: Leaderboard per weekly snapshot with tie-safe points rank,
--     each competitor's share of all points, and running (cumulative) share
CREATE OR REPLACE VIEW v_ranking_leaderboard AS
SELECT
    r.ranking_year,
    r.ranking_week,
    r.ranking_gender,
    co.competitor_id,
    co.name,
    co.country,
    co.country_code,
    r.`rank`,
    r.points,
    r.movement,
    r.competitions_played,
    DENSE_RANK() OVER (
        PARTITION BY r.ranking_year, r.ranking_week, r.ranking_gender
        ORDER BY r.points DESC
    ) AS points_dense_rank,
    ROUND(100.0 * r.points / SUM(r.points) OVER (
        PARTITION BY r.ranking_year, r.ranking_week, r.ranking_gender
    ), 2) AS pct_of_total_points,
    ROUND(100.0 * SUM(r.points) OVER (
        PARTITION BY r.ranking_year, r.ranking_week, r.ranking_gender
        ORDER BY r.`rank`, co.competitor_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / SUM(r.points) OVER (
        PARTITION BY r.ranking_year, r.ranking_week, r.ranking_gender
    ), 2) AS cumulative_pct_of_points
FROM Competitor_Rankings r
JOIN Competitors co ON r.competitor_id = co.competitor_id;

-- V2: How concentrated are points at the top of each ranking snapshot?
CREATE OR REPLACE VIEW v_points_concentration AS
SELECT
    ranking_year,
    ranking_week,
    ranking_gender,
    COUNT(*) AS competitors,
    SUM(points) AS total_points,
    SUM(CASE WHEN `rank` <= 10 THEN points ELSE 0 END) AS top10_points,
    ROUND(100.0 * SUM(CASE WHEN `rank` <= 10 THEN points ELSE 0 END) / SUM(points), 2) AS top10_share_pct
FROM Competitor_Rankings
GROUP BY ranking_year, ranking_week, ranking_gender;

-- V3: Rank history per competitor (needs 2 or more weekly snapshots to return changes)
--     LAG() looks at the same competitor's previous snapshot
CREATE OR REPLACE VIEW v_rank_history AS
SELECT
    r.competitor_id,
    co.name,
    co.country,
    r.ranking_gender,
    r.ranking_year,
    r.ranking_week,
    r.`rank`,
    r.points,
    LAG(r.`rank`) OVER (
        PARTITION BY r.competitor_id, r.ranking_gender
        ORDER BY r.ranking_year, r.ranking_week
    ) AS prev_rank,
    LAG(r.points) OVER (
        PARTITION BY r.competitor_id, r.ranking_gender
        ORDER BY r.ranking_year, r.ranking_week
    ) AS prev_points
FROM Competitor_Rankings r
JOIN Competitors co ON r.competitor_id = co.competitor_id;

-- V4: Competition counts by category, type, gender and level
CREATE OR REPLACE VIEW v_competition_summary AS
SELECT
    cat.category_name,
    c.type,
    c.gender,
    c.category_level,
    COUNT(*) AS competition_count
FROM Competitions c
JOIN Categories cat ON c.category_id = cat.category_id
GROUP BY cat.category_name, c.type, c.gender, c.category_level;
