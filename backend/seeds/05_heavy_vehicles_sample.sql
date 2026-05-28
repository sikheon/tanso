-- ============================================================
-- Sample heavy-truck vehicles for the demo (skip if already present)
-- ============================================================

INSERT INTO vehicles (plate, model, fuel_type, vehicle_class, year_produced, emission_factor_id)
SELECT
  v.plate, v.model, v.fuel_type, v.vehicle_class, v.year_produced,
  (SELECT id FROM emission_factors
   WHERE fuel_type = v.fuel_type AND vehicle_class = v.vehicle_class
   ORDER BY valid_from DESC LIMIT 1)
FROM (VALUES
  ('데모-디젤-8톤',     '메가트럭 8톤 (디젤)',    'diesel', 'truck_8t',  2023),
  ('데모-디젤-11톤',    '엑시언트 11톤 (디젤)',   'diesel', 'truck_11t', 2023),
  ('데모-디젤-25톤',    '대우 노부스 25톤 (디젤)', 'diesel', 'truck_25t', 2023),
  ('데모-트레일러-40톱', '트랙터 트레일러 40t (디젤)', 'diesel', 'trailer',  2023)
) AS v(plate, model, fuel_type, vehicle_class, year_produced)
WHERE NOT EXISTS (
  SELECT 1 FROM vehicles vv WHERE vv.plate = v.plate
);
