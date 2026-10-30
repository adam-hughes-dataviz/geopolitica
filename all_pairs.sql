-- GDELT events between every pair of countries, last 52 complete weeks, packed one row per pair.
-- Sports stories are left out (by web address), and a "war" count is added: fighting, assaults and mass
-- violence where BOTH sides are a government or military (w0, w1) or at least one side is (l0, l1),
-- over the last two 4-week periods.
-- Run in the BigQuery console, then Save results > JSON (local file) into the Geopolitica folder.
-- Cost: probably 5 to 15 GB processed (check "Bytes processed"), inside the free monthly allowance.
-- If the saved file is too large, raise min_events (for example to 3000) and run again.
DECLARE min_events INT64 DEFAULT 1000;
DECLARE anchor DATE DEFAULT DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY));

WITH e AS (
  SELECT
    LEAST(Actor1CountryCode, Actor2CountryCode) AS a,
    GREATEST(Actor1CountryCode, Actor2CountryCode) AS b,
    IF(Actor1CountryCode < Actor2CountryCode, 0, 1) AS i,
    EventRootCode AS r,
    AvgTone AS tone,
    QuadClass AS q,
    IF(EventRootCode IN ('18', '19', '20')
       AND Actor1Type1Code IN ('GOV', 'MIL') AND Actor2Type1Code IN ('GOV', 'MIL'), 1, 0) AS wf,
    -- looser test: state forces on at least one side (many events type only one actor, or none)
    IF(EventRootCode IN ('18', '19', '20')
       AND (Actor1Type1Code IN ('GOV', 'MIL') OR Actor2Type1Code IN ('GOV', 'MIL')), 1, 0) AS lf,
    DATE_DIFF(anchor, PARSE_DATE('%Y%m%d', CAST(SQLDATE AS STRING)), DAY) AS dd
  FROM `gdelt-bq.gdeltv2.events_partitioned`
  WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 372 DAY)
    AND Actor1CountryCode IS NOT NULL
    AND Actor2CountryCode IS NOT NULL
    AND Actor1CountryCode != Actor2CountryCode
    AND Actor1CountryCode NOT IN ('EUR', 'WST', 'ASA', 'AFR', 'LAM', 'MEA', 'SAS', 'SEA', 'NAM', 'CRB', 'SCN', 'BLK', 'BAL', 'NMR', 'SSA', 'PGS', 'WAF')
    AND Actor2CountryCode NOT IN ('EUR', 'WST', 'ASA', 'AFR', 'LAM', 'MEA', 'SAS', 'SEA', 'NAM', 'CRB', 'SCN', 'BLK', 'BAL', 'NMR', 'SSA', 'PGS', 'WAF')
    -- leave out sports coverage: sports sites and sports words in the article address
    AND NOT IFNULL(REGEXP_CONTAINS(SOURCEURL, r'(?i)(skysports|foxsports|espn|cricbuzz|cricinfo|eurosport|bleacherreport|goal\.com|sportstar|sportskeeda|sports\.|/sports?/|[/_-](cricket|football|soccer|rugby|tennis|golf|nba|nfl|nhl|mlb|fifa|uefa|olympics?|paralympics?|ipl|t20|premier-league|champions-league|world-cup|formula-?1|motogp|boxing|ufc|wwe|hockey|athletics|marathon|wimbledon)([/_.-]|$))'), FALSE)
),
g AS (
  -- p: 0 = last 4 weeks, 1 = the 4 before, 2 = the 5 before that (13 weeks in all), 3 = the rest of the year
  SELECT
    a, b, i, r,
    CASE WHEN DIV(dd - 1, 7) < 4 THEN 0 WHEN DIV(dd - 1, 7) < 8 THEN 1 WHEN DIV(dd - 1, 7) < 13 THEN 2 ELSE 3 END AS p,
    COUNT(*) AS n,
    SUM(tone) AS tone,
    COUNTIF(q IN (3, 4)) AS conf,
    SUM(wf) AS war,
    SUM(lf) AS loose
  FROM e
  WHERE dd BETWEEN 1 AND 364
  GROUP BY a, b, i, r, p
)
SELECT
  a,
  b,
  SUM(n) AS total,
  STRING_AGG(FORMAT('%d,%s,%d,%d,%d,%d', p, r, i, n, CAST(ROUND(tone) AS INT64), conf), ';' ORDER BY p, r, i) AS d,
  SUM(IF(p = 0, war, 0)) AS w0,
  SUM(IF(p = 1, war, 0)) AS w1,
  SUM(IF(p = 0, loose, 0)) AS l0,
  SUM(IF(p = 1, loose, 0)) AS l1
FROM g
GROUP BY a, b
HAVING SUM(n) >= min_events
ORDER BY total DESC
