-- ============================================================
-- Emission factors (g CO2/km) — research-corrected values
-- ============================================================
-- Source notes:
--   * Internal-combustion factors derived from Korea 공인연비
--     (한국에너지공단) measured CO2 for representative models, 2021–2023.
--   * Electric factors derived from 환경부 2023 power emission factor
--     0.4173 tCO2/MWh (= 417.3 g CO2/kWh) divided by representative
--     vehicle efficiency (km/kWh).
--   * Truck 2.5t/5t values are estimates pending official data.
-- ============================================================

INSERT INTO emission_factors (fuel_type, vehicle_class, g_per_km, source) VALUES
  -- Gasoline
  ('gasoline', 'compact', 106.00, '환경부 공인연비 2021 (모닝/아반떼 대표값)'),
  ('gasoline', 'sedan',   145.00, '환경부 공인연비 2021 (중형 1.6~2.0L 추정)'),
  ('gasoline', 'suv',     180.00, '환경부 공인연비 2021 (중형 SUV 추정)'),

  -- Diesel
  ('diesel', 'sedan',     130.00, '환경부 공인연비 2021 (디젤 승용 평균)'),
  ('diesel', 'suv',       134.00, '환경부 공인연비 2021 (쏘렌토/싼타페 평균)'),
  ('diesel', 'truck_1t',  215.00, '환경부 공인연비 2021 (봉고3 221, 포터2 204)'),
  ('diesel', 'truck_2_5t',280.00, '추정 (공식 g/km 데이터 부재)'),
  ('diesel', 'truck_5t',  400.00, '추정 (공식 g/km 데이터 부재)'),

  -- LPG
  ('lpg', 'sedan',        130.00, '환경부 공인연비 (가솔린 대비 약 10% 낮음)'),

  -- Hybrid
  ('hybrid', 'sedan',      79.00, '환경부 공인연비 2021 (쏘나타 HEV)'),
  ('hybrid', 'suv',        99.00, '환경부 공인연비 2021 (투싼 HEV)'),

  -- Electric (indirect emissions, 2023 grid factor 0.4173 tCO2/MWh)
  ('electric', 'compact',  60.00, '환경부 2023 전력배출계수 / 7.0 km/kWh'),
  ('electric', 'sedan',    79.00, '환경부 2023 전력배출계수 / 5.3 km/kWh'),
  ('electric', 'suv',      95.00, '환경부 2023 전력배출계수 / 4.4 km/kWh (추정)'),
  ('electric', 'truck_1t',119.00, '환경부 2023 전력배출계수 / 3.5 km/kWh (추정)');
