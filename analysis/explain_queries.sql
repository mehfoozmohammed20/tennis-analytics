-- ============================================================
-- EXPLAIN statements: evidence for the "query efficiency" criterion
-- Run each one in MySQL Workbench and read the output:
--   key   -> the index MySQL chose (NULL means no index was used)
--   type  -> 'ref' / 'range' / 'index' are good, 'ALL' means a full table scan
--   rows  -> estimated rows examined
-- Results are NOT recorded here on purpose: run them on your own data and note what you see.
-- Run database/upgrade_existing_db.sql first so the indexes below exist.
-- ============================================================

-- E1: venues filtered by country name (Q10) - expect idx_venues_country_name
EXPLAIN SELECT venue_name, city_name, country_name, timezone
FROM Venues WHERE country_name = 'Chile';

-- E2: venues for one complex (Q14) - expect idx_venues_complex
EXPLAIN SELECT v.venue_name FROM Venues v
JOIN Complexes cx ON v.complex_id = cx.complex_id
WHERE cx.complex_name = 'Nacional';

-- E3: competitions per category join (Q2) - expect idx_competitions_category
EXPLAIN SELECT cat.category_name, COUNT(*) FROM Competitions c
JOIN Categories cat ON c.category_id = cat.category_id
GROUP BY cat.category_name;

-- E4: latest ranking snapshot filter used by the app - expect idx_rankings_snapshot
EXPLAIN SELECT r.`rank`, r.points FROM Competitor_Rankings r
WHERE (r.ranking_year, r.ranking_week) = (
    SELECT ranking_year, ranking_week FROM Competitor_Rankings
    ORDER BY ranking_year DESC, ranking_week DESC LIMIT 1);

-- E5: competitors per country (Q19) - expect idx_competitors_country
EXPLAIN SELECT country, COUNT(*) FROM Competitors GROUP BY country;

-- E6: top 5 by rank (Q16) - expect idx_rankings_rank
EXPLAIN SELECT competitor_id, `rank` FROM Competitor_Rankings WHERE `rank` <= 5;
