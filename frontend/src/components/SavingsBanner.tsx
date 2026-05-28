"use client";

import type { Route, VRPResult } from "@/lib/types";

interface Props {
  routes?: Route[];          // for P2P / recalc payloads
  vrpResults?: VRPResult[];  // for VRP payload
  vehicleLabel?: string;
}

interface ComparisonBundle {
  ecoLabel: string;
  fastLabel: string;
  ecoCo2: number;
  fastCo2: number;
  ecoDistanceKm: number;
  fastDistanceKm: number;
  ecoDurationMin: number;
  fastDurationMin: number;
}

const PINE_PER_DAY_G = 18;

function pickBest<T>(items: T[], score: (it: T) => number): T | null {
  if (!items.length) return null;
  return items.reduce((best, cur) => (score(cur) < score(best) ? cur : best));
}

function buildBundleFromRoutes(routes: Route[]): ComparisonBundle | null {
  if (routes.length < 2) return null;
  const eco = pickBest(routes, (r) => r.total_co2_g);
  const fast = pickBest(routes, (r) => r.total_duration_s);
  if (!eco || !fast || eco === fast) return null;
  return {
    ecoLabel: `${eco.engine} / ${eco.objective}`,
    fastLabel: `${fast.engine} / ${fast.objective}`,
    ecoCo2: eco.total_co2_g,
    fastCo2: fast.total_co2_g,
    ecoDistanceKm: eco.total_distance_m / 1000,
    fastDistanceKm: fast.total_distance_m / 1000,
    ecoDurationMin: Math.round(eco.total_duration_s / 60),
    fastDurationMin: Math.round(fast.total_duration_s / 60),
  };
}

function buildBundleFromVRP(results: VRPResult[]): ComparisonBundle | null {
  if (results.length < 2) return null;
  const eco = results.find((r) => r.objective === "co2");
  const fast = results.find((r) => r.objective === "duration") ?? results.find((r) => r.objective === "distance");
  if (!eco || !fast || eco === fast) return null;
  return {
    ecoLabel: "CO₂ 최적",
    fastLabel: fast.objective === "duration" ? "시간 최단" : "거리 최단",
    ecoCo2: eco.total_co2_g,
    fastCo2: fast.total_co2_g,
    ecoDistanceKm: eco.total_distance_m / 1000,
    fastDistanceKm: fast.total_distance_m / 1000,
    ecoDurationMin: Math.round(eco.total_duration_s / 60),
    fastDurationMin: Math.round(fast.total_duration_s / 60),
  };
}

export default function SavingsBanner({ routes, vrpResults, vehicleLabel }: Props) {
  const bundle =
    routes && routes.length
      ? buildBundleFromRoutes(routes)
      : vrpResults && vrpResults.length
        ? buildBundleFromVRP(vrpResults)
        : null;

  if (!bundle) return null;

  const savedG = bundle.fastCo2 - bundle.ecoCo2;
  const savedPct = bundle.fastCo2 > 0 ? (savedG / bundle.fastCo2) * 100 : 0;
  const noSavings = savedG <= 0.5;

  if (noSavings) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
        🟰 친환경 경로와 빠른 경로의 CO₂ 차이가 거의 없습니다 — 이 구간에선 trade-off가 작음.
      </div>
    );
  }

  const pineDays = savedG / PINE_PER_DAY_G;
  const dist = bundle.ecoDistanceKm - bundle.fastDistanceKm;
  const dur = bundle.ecoDurationMin - bundle.fastDurationMin;
  const cost = (delta: number, unit: string) =>
    delta > 0 ? `+${delta.toFixed(unit === "km" ? 1 : 0)}${unit}` : `${delta.toFixed(unit === "km" ? 1 : 0)}${unit}`;

  return (
    <div className="rounded-xl border-2 border-eco-500 bg-gradient-to-br from-eco-50 to-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="text-3xl">🌱</div>
        <div className="flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-eco-700">
              −{Math.round(savedG).toLocaleString()} g
            </span>
            <span className="text-lg font-semibold text-eco-600">
              ({savedPct.toFixed(1)}%)
            </span>
            <span className="text-sm text-slate-500">CO₂ 절감</span>
          </div>
          <div className="mt-1 text-sm text-slate-700">
            <b>{bundle.ecoLabel}</b> 경로가 <b>{bundle.fastLabel}</b> 대비{" "}
            CO₂를 <b>{Math.round(savedG).toLocaleString()} g</b> 줄여줍니다
            {vehicleLabel && <span className="text-slate-500"> ({vehicleLabel})</span>}.
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
            <Cell label="거리 차이" value={cost(dist, " km")} muted />
            <Cell label="시간 차이" value={cost(dur, " 분")} muted />
            <Cell label="소나무 흡수" value={`≈ ${pineDays.toFixed(1)}일`} accent />
          </div>
        </div>
      </div>
    </div>
  );
}

function Cell({ label, value, muted, accent }: {
  label: string; value: string; muted?: boolean; accent?: boolean;
}) {
  return (
    <div className={`rounded-md border ${accent ? "border-eco-300 bg-eco-50" : "border-slate-200 bg-white"} p-2 text-center`}>
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className={`font-semibold ${accent ? "text-eco-700" : muted ? "text-slate-600" : "text-slate-700"}`}>
        {value}
      </div>
    </div>
  );
}
