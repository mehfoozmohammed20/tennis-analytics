Every field stored in the database: type, meaning, and where it comes from. Meanings follow the project brief and the actual API responses. "Derived" means computed by this project, not provided by the API.

### Categories — source: `/competitions` (nested `category` object)
| Field | Type | Meaning |
|---|---|---|
| category_id | VARCHAR(50), PK | SportRadar category ID (e.g. `sr:category:3`) |
| category_name | VARCHAR(100) | Category name (e.g. ATP, WTA) |

### Competitions — source: `/competitions`
| Field | Type | Meaning |
|---|---|---|
| competition_id | VARCHAR(50), PK | SportRadar competition ID |
| competition_name | VARCHAR(150) | Competition name |
| parent_id | VARCHAR(50), nullable | Parent competition ID as returned by the API. **Most values do not match any `competition_id` in the same response**, so this is not enforced as a foreign key (exact share on the Data Quality page) |
| type | VARCHAR(20) | `singles`, `doubles`, `mixed_doubles` or `mixed` (values observed in the data) |
| gender | VARCHAR(10) | `men`, `women` or `mixed` |
| category_id | VARCHAR(50), FK | Link to Categories |
| category_level | VARCHAR(30), nullable | Tournament tier from the API's `level` field (e.g. `grand_slam`, `atp_250`). Not present on every competition |

### Complexes — source: `/complexes`
| Field | Type | Meaning |
|---|---|---|
| complex_id | VARCHAR(50), PK | SportRadar complex ID |
| complex_name | VARCHAR(100) | Name of the sports complex |

### Venues — source: `/complexes` (nested `venues` array)
| Field | Type | Meaning |
|---|---|---|
| venue_id | VARCHAR(50), PK | SportRadar venue ID |
| venue_name | VARCHAR(100) | Venue (court/stadium) name |
| city_name | VARCHAR(100) | City |
| country_name | VARCHAR(100) | Country |
| country_code | CHAR(3) | 3-letter country code as returned (e.g. `CHL`); looks like ISO 3166-1 alpha-3, not independently verified |
| timezone | VARCHAR(100) | IANA timezone name (e.g. `America/Santiago`) |
| complex_id | VARCHAR(50), FK | Link to Complexes |

### Competitors — source: `/double_competitors_rankings` (nested `competitor`)
| Field | Type | Meaning |
|---|---|---|
| competitor_id | VARCHAR(50), PK | SportRadar competitor ID |
| name | VARCHAR(100) | Competitor name (format `Surname, Given`) |
| country | VARCHAR(100) | Country name |
| country_code | CHAR(3) | 3-letter country code as returned |
| abbreviation | VARCHAR(10) | Shortened name |

### Competitor_Rankings — source: `/double_competitors_rankings`
| Field | Type | Meaning |
|---|---|---|
| rank_id | INT, PK, auto | Surrogate key (derived) |
| `rank` | INT | Rank in that snapshot. Ties exist and are valid. Backticked because RANK is reserved in MySQL 8 |
| movement | INT | Rank change compared with the previous week (per the brief) |
| points | INT | Ranking points |
| competitions_played | INT | Number of competitions played (per the brief) |
| ranking_year | INT | Year of the weekly snapshot (snapshot-level field in the API) |
| ranking_week | INT | Week number of the snapshot |
| ranking_gender | VARCHAR(10) | Gender of the ranking list (`men`, `women`) |
| competitor_id | VARCHAR(50), FK | Link to Competitors |

Unique key: `(competitor_id, ranking_year, ranking_week, ranking_gender)` — one row per competitor per weekly snapshot, which is what lets weekly runs accumulate history.

### ETL_Run_Log — derived (audit table)
| Field | Type | Meaning |
|---|---|---|
| run_id | INT, PK, auto | Run number |
| run_at | DATETIME | When the run was logged |
| status | VARCHAR(20) | `SUCCESS` or `FAILED` |
| details | TEXT | JSON: duration, loaded counts, view status or the error |

### Views — derived (`database/views.sql`)
| View | Purpose |
|---|---|
| v_ranking_leaderboard | Per snapshot: tie-safe points rank (DENSE_RANK), share of total points, cumulative share |
| v_points_concentration | Share of all points held by competitors ranked 10th or better, per snapshot |
| v_rank_history | Previous rank/points per competitor (LAG); needs two or more weekly snapshots |
| v_competition_summary | Competition counts by category, type, gender and level |
