-- New vs returning: 1-click should help first-time checkout more.
SELECT
  user_type,
  variant,
  COUNT(*) AS users,
  ROUND(AVG(purchased), 4) AS conversion,
  ROUND(AVG(revenue), 2) AS revenue_per_user
FROM assignments
GROUP BY user_type, variant
ORDER BY user_type, variant;
