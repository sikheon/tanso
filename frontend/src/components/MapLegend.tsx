"use client";

import type { Route, VRPResult } from "@/lib/types";

interface Props {
  routes?: Route[];
  vrpResults?: VRPResult[];
  onHover?: (routeId: number | null) => void;
}

const ENGINE_COLOR: Record<string, string> = {
  kakao: "#3b82f6",
  ors: "#a855f7",
  or_tools_vrp: "#10b981",
};

const ENGINE_LABEL: Record<string, string> = {
  kakao: "Kakao 네비",
  ors: "ORS (벤치마크)",
  or_tools_vrp: "VRP",
};

const OBJECTIVE_LABEL: Record<string, string> = {
  recommend: "추천",
  fastest: "최단시간",
  shortest: "최단거리",
  alternative: "대안",
  co2_min: "CO₂ 최소",
  duration_min: "시간 최소",
  distance_min: "거리 최소",
};

export default function MapLegend({ routes = [], vrpResults = [], onHover }: Props) {
  // Build legend entries from either P2P routes or VRP results
  const entries: {
    id?: number | null;
    color: string;
    engine: string;
    objective: string;
    distanceKm: number;
    durationMin: number;
    co2G: number;
    isRecommended: boolean;
  }[] = [];

  for (const r of routes) {
    entries.push({
      id: r.id ?? null,
      color: ENGINE_COLOR[r.engine] ?? "#64748b",
      engine: ENGINE_LABEL[r.engine] ?? r.engine,
      objective: OBJECTIVE_LABEL[r.objective] ?? r.objective,
      distanceKm: r.total_distance_m / 1000,
      durationMin: Math.round(r.total_duration_s / 60),
      co2G: r.total_co2_g,
      isRecommended: r.is_recommended,
    });
  }
  for (const r of vrpResults) {
    entries.push({
      id: null,
      color: ENGINE_COLOR.or_tools_vrp,
      engine: "OR-Tools",
      objective: OBJECTIVE_LABEL[`${r.objective}_min`] ?? r.objective,
      distanceKm: r.total_distance_m / 1000,
      durationMin: Math.round(r.total_duration_s / 60),
      co2G: r.total_co2_g,
      isRecommended: r.is_recommended,
    });
  }

  if (entries.length === 0) return null;

  return (
    <div className="pointer-events-auto absolute right-3 top-3 z-[1000] w-64 rounded-lg border border-slate-200 bg-white/95 p-3 shadow-md backdrop-blur">
      <div className="mb-2 text-[11px] font-bold uppercase tracking-wide text-slate-500">
        경로 비교 ({entries.length})
      </div>
      <div className="space-y-1.5">
        {entries.map((e, i) => (
          <div
            key={`${e.engine}-${e.objective}-${i}`}
            onMouseEnter={() => onHover?.(e.id ?? null)}
            onMouseLeave={() => onHover?.(null)}
            className={`flex cursor-default items-center gap-2 rounded-md p-1.5 text-xs transition ${
              e.isRecommended ? "bg-eco-50" : "hover:bg-slate-50"
            }`}
          >
            <span
              className="inline-block h-1 w-6 flex-shrink-0 rounded-full"
              style={{ backgroundColor: e.color, height: e.isRecommended ? 4 : 2 }}
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1 font-semibold text-slate-700">
                {e.isRecommended && <span>🌱</span>}
                <span className="truncate">{e.engine}</span>
                <span className="text-slate-400">·</span>
                <span className="text-slate-500">{e.objective}</span>
              </div>
              <div className="text-[10px] text-slate-500">
                {e.distanceKm.toFixed(1)}km · {e.durationMin}분 ·{" "}
                <span className={e.isRecommended ? "font-semibold text-eco-700" : ""}>
                  {Math.round(e.co2G).toLocaleString()}g CO₂
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
