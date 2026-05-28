-- ============================================================
-- Speed-bin emission multipliers (COPERT-style simplified)
-- ============================================================
-- Reference: EEA EMEP/EEA air pollutant emission inventory guidebook,
--            simplified to 8 bins. Real-world COPERT v5 uses
--            polynomial speed-emission curves; this is a discretized
--            approximation suitable for MVP.
--
-- `applies_to` values:
--   'all'           — applied to all engines (default)
--   'static_only'   — applied only to engines that do NOT include
--                     live traffic (e.g., ORS). Skipped for Kakao
--                     to avoid double-counting congestion effects.
--   'dynamic_only'  — applied only to engines that include live
--                     traffic (rarely used; reserved for future).
-- ============================================================

INSERT INTO speed_bin_factors (speed_min_kmh, speed_max_kmh, multiplier, applies_to) VALUES
  (  0.00,  10.00, 1.65, 'all'),   -- 극심 정체
  ( 10.00,  20.00, 1.35, 'all'),   -- 혼잡
  ( 20.00,  40.00, 1.10, 'all'),   -- 보통
  ( 40.00,  60.00, 1.00, 'all'),   -- 원활 (기준)
  ( 60.00,  80.00, 0.95, 'all'),   -- 고속 (효율 최적)
  ( 80.00, 100.00, 1.05, 'all'),   -- 고속
  (100.00, 120.00, 1.20, 'all'),   -- 고속
  (120.00, 999.99, 1.40, 'all');   -- 과속
