"use client";

import { useState } from "react";

import PlaceSearch from "@/components/PlaceSearch";
import VehicleSelector from "@/components/VehicleSelector";
import { api } from "@/lib/api";
import { useEloStore } from "@/store/useEloStore";

interface CoordInput {
  lat: string;
  lng: string;
  address: string;
}

const EMPTY: CoordInput = { lat: "", lng: "", address: "" };

const PRESETS: { label: string; value: CoordInput }[] = [
  { label: "서울역",   value: { lat: "37.5547", lng: "126.972",  address: "서울역" } },
  { label: "부산역",   value: { lat: "35.1147", lng: "129.0413", address: "부산역" } },
  { label: "강남구청", value: { lat: "37.5172", lng: "127.0473", address: "강남구청" } },
  { label: "인천공항", value: { lat: "37.4602", lng: "126.4407", address: "인천국제공항" } },
];

const WAYPOINT_PRESETS: { label: string; value: CoordInput }[] = [
  { label: "대전역",   value: { lat: "36.3320", lng: "127.4344", address: "대전역" } },
  { label: "대구역",   value: { lat: "35.8780", lng: "128.6285", address: "대구역" } },
  { label: "광주역",   value: { lat: "35.1644", lng: "126.9095", address: "광주역" } },
  { label: "수원역",   value: { lat: "37.2664", lng: "127.0006", address: "수원역" } },
];

function parseCoord(c: CoordInput): { lat: number; lng: number; address?: string } | null {
  const lat = Number(c.lat), lng = Number(c.lng);
  if (Number.isNaN(lat) || Number.isNaN(lng)) return null;
  return { lat, lng, address: c.address || undefined };
}

export default function InputPanelP2P() {
  const [origin, setOrigin] = useState<CoordInput>(PRESETS[0].value);
  const [destination, setDestination] = useState<CoordInput>(PRESETS[1].value);
  const [waypoints, setWaypoints] = useState<CoordInput[]>([]);
  const [co2Weight, setCo2Weight] = useState(0.6);
  const selectedVehicleId = useEloStore((s) => s.selectedVehicleId);
  const setCurrentRun = useEloStore((s) => s.setCurrentRun);
  const setLoading = useEloStore((s) => s.setLoading);
  const setError = useEloStore((s) => s.setError);
  const loadHistory = useEloStore((s) => s.loadHistory);
  const loading = useEloStore((s) => s.loading);

  function addWaypoint() {
    if (waypoints.length >= 10) return;
    setWaypoints([...waypoints, { ...EMPTY }]);
  }

  function updateWaypoint(idx: number, patch: Partial<CoordInput>) {
    setWaypoints(waypoints.map((w, i) => (i === idx ? { ...w, ...patch } : w)));
  }

  function removeWaypoint(idx: number) {
    setWaypoints(waypoints.filter((_, i) => i !== idx));
  }

  async function submit() {
    if (!selectedVehicleId) {
      setError("차량을 먼저 선택하세요");
      return;
    }
    const o = parseCoord(origin), d = parseCoord(destination);
    if (!o || !d) {
      setError("출발지/도착지 좌표가 올바르지 않습니다");
      return;
    }
    const validWaypoints = waypoints
      .map((w) => parseCoord(w))
      .filter((w): w is { lat: number; lng: number; address?: string } => w !== null);

    setError(null);
    setLoading(true);
    try {
      const remaining = (1 - co2Weight) / 2;
      const resp = await api.p2p({
        origin: o,
        destination: d,
        waypoints: validWaypoints.length > 0 ? validWaypoints : undefined,
        vehicle_id: selectedVehicleId,
        options: {
          engines: ["kakao", "ors"],
          alternatives_per_engine: 2,
          weights: { distance: remaining, duration: remaining, co2: co2Weight },
          generate_narrative: true,
        },
      });
      setCurrentRun({ kind: "p2p", payload: resp });
      await loadHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <PointInput
        label="🚩 출발지"
        value={origin}
        onChange={setOrigin}
        presets={PRESETS}
        accent="emerald"
      />

      {waypoints.length > 0 && (
        <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50/40 p-2">
          <div className="text-xs font-semibold text-amber-800">
            📍 경유지 ({waypoints.length})
          </div>
          {waypoints.map((w, i) => (
            <PointInput
              key={i}
              label={`경유 #${i + 1}`}
              value={w}
              onChange={(v) => updateWaypoint(i, v)}
              presets={WAYPOINT_PRESETS}
              compact
              accent="amber"
              onRemove={() => removeWaypoint(i)}
            />
          ))}
        </div>
      )}

      {waypoints.length < 10 && (
        <button
          onClick={addWaypoint}
          className="w-full rounded-md border border-dashed border-amber-300 bg-amber-50/50 px-3 py-1.5 text-xs text-amber-700 hover:bg-amber-100"
        >
          + 경유지 추가 ({waypoints.length}/10)
        </button>
      )}

      <PointInput
        label="🏁 도착지"
        value={destination}
        onChange={setDestination}
        presets={PRESETS}
        accent="rose"
      />

      <VehicleSelector />

      <label className="block">
        <span className="mb-1 block text-sm font-medium text-slate-700">
          🌱 CO₂ 우선도: <span className="font-semibold text-eco-700">{(co2Weight * 100).toFixed(0)}%</span>
        </span>
        <input
          type="range" min={0} max={1} step={0.1} value={co2Weight}
          onChange={(e) => setCo2Weight(Number(e.target.value))}
          className="w-full accent-eco-600"
        />
        <div className="flex justify-between text-xs text-slate-500">
          <span>속도/거리 우선</span><span>탄소 절감 우선</span>
        </div>
      </label>

      <button
        disabled={loading}
        onClick={submit}
        className="w-full rounded-md bg-eco-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-eco-700 disabled:cursor-wait disabled:opacity-60"
      >
        {loading ? "분석 중..." : "🌱 친환경 경로 찾기"}
      </button>
    </div>
  );
}

function PointInput({
  label, value, onChange, presets, accent = "slate", compact = false, onRemove,
}: {
  label: string;
  value: CoordInput;
  onChange: (v: CoordInput) => void;
  presets: { label: string; value: CoordInput }[];
  accent?: "emerald" | "rose" | "amber" | "slate";
  compact?: boolean;
  onRemove?: () => void;
}) {
  const accentClass = {
    emerald: "text-emerald-700",
    rose:    "text-rose-700",
    amber:   "text-amber-700",
    slate:   "text-slate-700",
  }[accent];

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className={`block text-sm font-medium ${accentClass}`}>{label}</span>
        {onRemove && (
          <button
            onClick={onRemove}
            className="text-xs text-rose-500 hover:text-rose-700"
          >
            ✕ 삭제
          </button>
        )}
      </div>
      <div className="space-y-1">
        <PlaceSearch
          placeholder={`${label.replace(/^[^A-Za-z가-힣]+/, "")} 검색`}
          onPick={(item) =>
            onChange({
              lat: String(item.lat),
              lng: String(item.lng),
              address: item.name,
            })
          }
        />
        <input
          type="text" placeholder="주소 별칭"
          value={value.address}
          onChange={(e) => onChange({ ...value, address: e.target.value })}
          className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-eco-500 focus:outline-none focus:ring-1 focus:ring-eco-500"
        />
        <div className="grid grid-cols-2 gap-1">
          <input
            type="number" step="0.0001" placeholder="lat"
            value={value.lat}
            onChange={(e) => onChange({ ...value, lat: e.target.value })}
            className="rounded-md border border-slate-300 px-2 py-1 text-xs"
          />
          <input
            type="number" step="0.0001" placeholder="lng"
            value={value.lng}
            onChange={(e) => onChange({ ...value, lng: e.target.value })}
            className="rounded-md border border-slate-300 px-2 py-1 text-xs"
          />
        </div>
        {!compact && (
          <div className="flex flex-wrap gap-1">
            {presets.map((p) => (
              <button
                key={p.label}
                onClick={() => onChange(p.value)}
                className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs text-slate-600 hover:bg-slate-100"
              >
                {p.label}
              </button>
            ))}
          </div>
        )}
        {compact && (
          <div className="flex flex-wrap gap-1">
            {presets.map((p) => (
              <button
                key={p.label}
                onClick={() => onChange(p.value)}
                className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] text-amber-700 hover:bg-amber-100"
              >
                {p.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
