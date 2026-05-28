"use client";

import { useEloStore } from "@/store/useEloStore";

const FUEL_LABEL: Record<string, string> = {
  gasoline: "휘발유",
  diesel: "경유",
  lpg: "LPG",
  hybrid: "하이브리드",
  electric: "전기",
};

const CLASS_LABEL: Record<string, string> = {
  compact: "경차/소형",
  sedan: "승용",
  suv: "SUV",
  truck_1t: "1톤 트럭",
  truck_2_5t: "2.5톤 트럭",
  truck_5t: "5톤 트럭",
  truck_8t: "8톤 트럭",
  truck_11t: "11톤 트럭",
  truck_25t: "25톤 대형트럭",
  trailer: "트레일러 (40톤+)",
};

export default function VehicleSelector() {
  const vehicles = useEloStore((s) => s.vehicles);
  const selectedId = useEloStore((s) => s.selectedVehicleId);
  const setVehicleId = useEloStore((s) => s.setVehicleId);

  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">
        🚗 차종
      </span>
      <select
        value={selectedId ?? ""}
        onChange={(e) => setVehicleId(Number(e.target.value))}
        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-eco-500 focus:outline-none focus:ring-1 focus:ring-eco-500"
      >
        {vehicles.length === 0 && <option value="">차량 로딩 중...</option>}
        {vehicles.map((v) => (
          <option key={v.id} value={v.id}>
            {v.model ?? `#${v.id}`}
            {" — "}
            {FUEL_LABEL[v.fuel_type] ?? v.fuel_type} {CLASS_LABEL[v.vehicle_class] ?? v.vehicle_class}
            {" ("}
            {v.emission_factor_g_per_km?.toFixed(0)} g/km)
          </option>
        ))}
      </select>
    </label>
  );
}
