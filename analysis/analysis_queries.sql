-- ============================================================
-- SportRadar Tennis Analytics — Mandatory Analytical Queries
-- ============================================================

-- ============================================================
-- SECTION 1: COMPETITIONS
-- ============================================================

-- Q1: List all competitions along with their category name
SELECT c.competition_id, c.competition_name, c.type, c.gender, cat.category_name
FROM Competitions c
JOIN Categories cat ON c.category_id = cat.category_id;

-- Q2: Count the number of competitions in each category
SELECT cat.category_name, COUNT(*) AS competition_count
FROM Competitions c
JOIN Categories cat ON c.category_id = cat.category_id
GROUP BY cat.category_name
ORDER BY competition_count DESC;

-- Q3: Find all competitions of type 'doubles'
SELECT competition_id, competition_name, gender, category_id
FROM Competitions
WHERE type = 'doubles';

-- Q4: Get competitions that belong to a specific category (e.g., ITF Men)
SELECT c.competition_id, c.competition_name, c.type, c.gender
FROM Competitions c
JOIN Categories cat ON c.category_id = cat.category_id
WHERE cat.category_name = 'ITF Men';   -- swap value as needed

-- Q5: Identify parent competitions and their sub-competitions
SELECT parent.competition_name AS parent_competition,
       child.competition_name  AS sub_competition,
       child.type, child.gender
FROM Competitions child
JOIN Competitions parent ON child.parent_id = parent.competition_id
ORDER BY parent.competition_name;

-- Q6: Analyze the distribution of competition types by category
SELECT cat.category_name, c.type, COUNT(*) AS count
FROM Competitions c
JOIN Categories cat ON c.category_id = cat.category_id
GROUP BY cat.category_name, c.type
ORDER BY cat.category_name, count DESC;

-- Q7: List all competitions with no parent (top-level competitions)
SELECT competition_id, competition_name, type, gender, category_id
FROM Competitions
WHERE parent_id IS NULL;


-- ============================================================
-- SECTION 2: COMPLEXES & VENUES
-- ============================================================

-- Q8: List all venues along with their associated complex name
SELECT v.venue_id, v.venue_name, cx.complex_name, v.city_name, v.country_name
FROM Venues v
JOIN Complexes cx ON v.complex_id = cx.complex_id;

-- Q9: Count the number of venues in each complex
SELECT cx.complex_name, COUNT(v.venue_id) AS venue_count
FROM Complexes cx
LEFT JOIN Venues v ON cx.complex_id = v.complex_id
GROUP BY cx.complex_name
ORDER BY venue_count DESC;

-- Q10: Get details of venues in a specific country (e.g., Chile)
SELECT venue_name, city_name, country_name, timezone
FROM Venues
WHERE country_name = 'Chile';   -- swap value as needed

-- Q11: Identify all venues and their timezones
SELECT venue_name, city_name, country_name, timezone
FROM Venues
ORDER BY timezone;

-- Q12: Find complexes that have more than one venue
SELECT cx.complex_name, COUNT(v.venue_id) AS venue_count
FROM Complexes cx
JOIN Venues v ON cx.complex_id = v.complex_id
GROUP BY cx.complex_name
HAVING COUNT(v.venue_id) > 1
ORDER BY venue_count DESC;

-- Q13: List venues grouped by country
SELECT country_name, GROUP_CONCAT(venue_name SEPARATOR ', ') AS venues
FROM Venues
GROUP BY country_name
ORDER BY country_name;

-- Q14: Find all venues for a specific complex (e.g., Nacional)
SELECT v.venue_name, v.city_name, v.country_name, v.timezone
FROM Venues v
JOIN Complexes cx ON v.complex_id = cx.complex_id
WHERE cx.complex_name = 'Nacional';   -- swap value as needed


-- ============================================================
-- SECTION 3: RANKINGS & COMPETITORS
-- ============================================================

-- Q15: Get all competitors with their rank and points
-- (latest weekly snapshot only: rankings accumulate week over week, so without this each competitor appears once per stored week)
SELECT co.name, co.country, r.`rank`, r.points, r.ranking_year, r.ranking_week
FROM Competitor_Rankings r
JOIN Competitors co ON r.competitor_id = co.competitor_id
WHERE (r.ranking_year, r.ranking_week) = (
    SELECT ranking_year, ranking_week FROM Competitor_Rankings
    ORDER BY ranking_year DESC, ranking_week DESC LIMIT 1)
ORDER BY r.`rank`;

-- Q16: Find competitors ranked in the top 5
-- (latest snapshot, the men's and women's ranking lists each have their own top 5)
SELECT co.name, co.country, r.`rank`, r.points, r.ranking_gender
FROM Competitor_Rankings r
JOIN Competitors co ON r.competitor_id = co.competitor_id
WHERE r.`rank` <= 5
  AND (r.ranking_year, r.ranking_week) = (
    SELECT ranking_year, ranking_week FROM Competitor_Rankings
    ORDER BY ranking_year DESC, ranking_week DESC LIMIT 1)
ORDER BY r.ranking_gender, r.`rank`;

-- Q17: List competitors with no rank movement (stable rank)
-- (latest weekly snapshot only)
SELECT co.name, co.country, r.`rank`, r.points, r.movement
FROM Competitor_Rankings r
JOIN Competitors co ON r.competitor_id = co.competitor_id
WHERE r.movement = 0
  AND (r.ranking_year, r.ranking_week) = (
    SELECT ranking_year, ranking_week FROM Competitor_Rankings
    ORDER BY ranking_year DESC, ranking_week DESC LIMIT 1)
ORDER BY r.`rank`;

-- Q18: Get the total points of competitors from a specific country (e.g., Croatia)
-- (latest weekly snapshot only, summing across stored weeks would count the same points twice)
SELECT co.country, SUM(r.points) AS total_points
FROM Competitor_Rankings r
JOIN Competitors co ON r.competitor_id = co.competitor_id
WHERE co.country = 'Croatia'   -- swap value as needed
  AND (r.ranking_year, r.ranking_week) = (
    SELECT ranking_year, ranking_week FROM Competitor_Rankings
    ORDER BY ranking_year DESC, ranking_week DESC LIMIT 1)
GROUP BY co.country;

-- Q19: Count the number of competitors per country
SELECT country, COUNT(*) AS competitor_count
FROM Competitors
GROUP BY country
ORDER BY competitor_count DESC;

-- Q20: Find competitors with the highest points in the current week
SELECT co.name, co.country, r.points, r.ranking_year, r.ranking_week
FROM Competitor_Rankings r
JOIN Competitors co ON r.competitor_id = co.competitor_id
WHERE r.ranking_year = (SELECT MAX(ranking_year) FROM Competitor_Rankings)
  AND r.ranking_week = (SELECT MAX(ranking_week) FROM Competitor_Rankings
                          WHERE ranking_year = (SELECT MAX(ranking_year) FROM Competitor_Rankings))
ORDER BY r.points DESC
LIMIT 10;


-- ============================================================
-- ADDITIONAL ANALYTICAL QUERIES (beyond mandatory list)
-- ============================================================

-- A1: Which countries have the highest average points per competitor?
SELECT co.country, ROUND(AVG(r.points), 1) AS avg_points, COUNT(DISTINCT co.competitor_id) AS competitors
FROM Competitor_Rankings r
JOIN Competitors co ON r.competitor_id = co.competitor_id
WHERE (r.ranking_year, r.ranking_week) = (
    SELECT ranking_year, ranking_week FROM Competitor_Rankings
    ORDER BY ranking_year DESC, ranking_week DESC LIMIT 1)
GROUP BY co.country
HAVING competitors >= 2   -- avoid single-competitor skew
ORDER BY avg_points DESC
LIMIT 10;

-- A2: Largest positive rank movement (biggest risers)
SELECT co.name, co.country, r.movement, r.`rank`
FROM Competitor_Rankings r
JOIN Competitors co ON r.competitor_id = co.competitor_id
WHERE (r.ranking_year, r.ranking_week) = (
    SELECT ranking_year, ranking_week FROM Competitor_Rankings
    ORDER BY ranking_year DESC, ranking_week DESC LIMIT 1)
ORDER BY r.movement DESC
LIMIT 10;

-- A4: Points-per-competition efficiency (denominator-based, not raw totals) —
-- who earns the most per event played, not just who's played the most
SELECT co.name, co.country, r.points, r.competitions_played,
       ROUND(r.points / NULLIF(r.competitions_played, 0), 1) AS points_per_competition
FROM Competitor_Rankings r
JOIN Competitors co ON r.competitor_id = co.competitor_id
WHERE r.competitions_played > 0
  AND (r.ranking_year, r.ranking_week) = (
    SELECT ranking_year, ranking_week FROM Competitor_Rankings
    ORDER BY ranking_year DESC, ranking_week DESC LIMIT 1)
ORDER BY points_per_competition DESC
LIMIT 10;

-- A3: How deep is the competition hierarchy? (competitions that are themselves parents of parents)
SELECT c1.competition_name AS grandparent, c2.competition_name AS parent, c3.competition_name AS child
FROM Competitions c3
JOIN Competitions c2 ON c3.parent_id = c2.competition_id
JOIN Competitions c1 ON c2.parent_id = c1.competition_id;

-- A5: Tournament tier distribution (uses the API's `level` field)
SELECT category_level, type, COUNT(*) AS competitions
FROM Competitions
WHERE category_level IS NOT NULL
GROUP BY category_level, type
ORDER BY category_level, competitions DESC;

-- A6: Verify the parent_id finding: which parent_ids never appear as a competition_id?
SELECT c.parent_id, COUNT(*) AS children
FROM Competitions c
LEFT JOIN Competitions p ON c.parent_id = p.competition_id
WHERE c.parent_id IS NOT NULL AND p.competition_id IS NULL
GROUP BY c.parent_id
ORDER BY children DESC
LIMIT 10;

-- ============================================================
-- WINDOW-FUNCTION QUERIES (use the views in database/views.sql, MySQL 8+)
-- ============================================================

-- W1: How concentrated are points at the top of each ranking snapshot?
SELECT * FROM v_points_concentration
ORDER BY ranking_year DESC, ranking_week DESC, ranking_gender;

-- W2: Leaderboard with tie-safe points rank, share of points and running share
SELECT ranking_gender, `rank`, name, country, points, points_dense_rank,
       pct_of_total_points, cumulative_pct_of_points
FROM v_ranking_leaderboard
WHERE (ranking_year, ranking_week) = (
    SELECT ranking_year, ranking_week FROM Competitor_Rankings
    ORDER BY ranking_year DESC, ranking_week DESC LIMIT 1)
ORDER BY ranking_gender, `rank`
LIMIT 20;

-- W3: Biggest risers between the two latest snapshots (returns rows only once 2+ weeks are loaded)
SELECT name, country, ranking_gender, prev_rank, `rank`, (prev_rank - `rank`) AS places_gained
FROM v_rank_history
WHERE (ranking_year, ranking_week) = (
    SELECT ranking_year, ranking_week FROM Competitor_Rankings
    ORDER BY ranking_year DESC, ranking_week DESC LIMIT 1)
  AND prev_rank IS NOT NULL
ORDER BY places_gained DESC
LIMIT 10;

-- W4: Countries with a minimum sample size, so tiny samples cannot top the average
SELECT co.country, COUNT(DISTINCT co.competitor_id) AS competitors,
       ROUND(AVG(r.points), 1) AS avg_points
FROM Competitor_Rankings r
JOIN Competitors co ON r.competitor_id = co.competitor_id
GROUP BY co.country
HAVING COUNT(DISTINCT co.competitor_id) >= 3
ORDER BY avg_points DESC;

