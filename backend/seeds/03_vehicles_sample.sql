-- ============================================================
-- Sample vehicle records (demo / development)
-- ============================================================
-- These link to emission_factors via emission_factor_id.
-- The subquery resolves the latest factor for each (fuel,class) pair.
-- ============================================================

INSERT INTO vehicles (plate, model, fuel_type, vehicle_class, year_produced, emission_factor_id) VALUES
  ('데모-가솔린-중형', '쏘나타 (가솔린)',    'gasoline', 'sedan',
    2023, (SELECT id FROM emission_factors WHERE fuel_type='gasoline' AND vehicle_class='sedan'  LIMIT 1)),
  ('데모-디젤-1톤',    '봉고3 1톤 (디젤)',   'diesel',   'truck_1t',
    2023, (SELECT id FROM emission_factors WHERE fuel_type='diesel'   AND vehicle_class='truck_1t' LIMIT 1)),
  ('데모-디젤-2.5톤',  '마이티 2.5톤 (디젤)', 'diesel',   'truck_2_5t',
    2023, (SELECT id FROM emission_factors WHERE fuel_type='diesel'   AND vehicle_class='truck_2_5t' LIMIT 1)),
  ('데모-LPG-승용',    '쏘나타 (LPG)',       'lpg',      'sedan',
    2023, (SELECT id FROM emission_factors WHERE fuel_type='lpg'      AND vehicle_class='sedan' LIMIT 1)),
  ('데모-하이브리드',  '쏘나타 HEV',         'hybrid',   'sedan',
    2023, (SELECT id FROM emission_factors WHERE fuel_type='hybrid'   AND vehicle_class='sedan' LIMIT 1)),
  ('데모-전기-승용',   '아이오닉5 (EV)',      'electric', 'sedan',
    2023, (SELECT id FROM emission_factors WHERE fuel_type='electric' AND vehicle_class='sedan' LIMIT 1)),
  ('데모-전기-1톤',    '봉고3 EV',           'electric', 'truck_1t',
    2023, (SELECT id FROM emission_factors WHERE fuel_type='electric' AND vehicle_class='truck_1t' LIMIT 1));
