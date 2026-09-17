-- Overall conversion and revenue per assigned user (intent-to-treat).
SELECT
  variant,
  COUNT(*) AS users,
  SUM(purchased) AS buyers,
  ROUND(AVG(purchased), 4) AS conversion,
  ROUND(AVG(revenue), 2) AS revenue_per_user,
  ROUND(AVG(CASE WHEN purchased = 1 THEN revenue END), 2) AS aov
FROM assignments
GROUP BY variant;

-- Segments: device is the decision split.
SELECT
  device,
  variant,
  COUNT(*) AS users,
  ROUND(AVG(purchased), 4) AS conversion,
  ROUND(AVG(revenue), 2) AS revenue_per_user
FROM assignments
GROUP BY device, variant
ORDER BY device, variant;
