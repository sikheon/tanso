-- ============================================================
-- Heavy trucks (8t / 11t / 25t / trailer 40t+) — diesel
-- ============================================================
-- Source notes:
--   * 한국 공식 g/km 데이터 부재. 추정치는 EEA EMEP/EEA HDV
--     emission factors (kg CO2/km by GVW class) + 국내 평균
--     운행조건 가정 (적재율 60%, 도시간 혼합).
--   * 운영 시 차량별 실측 평균으로 대체 권장.
-- Inserts are idempotent via ON CONFLICT (fuel_type, vehicle_class, valid_from).
-- ============================================================

INSERT INTO emission_factors (fuel_type, vehicle_class, g_per_km, source) VALUES
  ('diesel', 'truck_8t',  560.00, '추정 (EEA HDV 7.5–12t 기준, 60% 적재)'),
  ('diesel', 'truck_11t', 720.00, '추정 (EEA HDV 12–14t 기준, 60% 적재)'),
  ('diesel', 'truck_25t', 950.00, '추정 (EEA HDV 20–28t 기준, 60% 적재)'),
  ('diesel', 'trailer',  1200.00, '추정 (EEA HDV 34–40t articulated, 트랙터+트레일러)')
ON CONFLICT (fuel_type, vehicle_class, valid_from) DO UPDATE
  SET g_per_km = EXCLUDED.g_per_km, source = EXCLUDED.source;
