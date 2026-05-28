"use client";

import clsx from "clsx";

import type { Route } from "@/lib/types";

const ENGINE_LABEL: Record<string, string> = {
  kakao: "Kakao",
  ors: "ORS",
  or_tools_vrp: "OR-Tools",
};

const OBJECTIVE_LABEL: Record<string, string> = {
  recommend: "추천",
  fastest: "최단시간",
  shortest: "최단거리",
  alternative: "대안",
  co2_min: "CO₂ 최소",
  distance_min: "거리 최소",
  duration_min: "시간 최소",
};

interface Props {
  routes: Route[];
  onHover?: (routeId: number | null) => void;
}

export default function RouteCards({ routes, onHover }: Props) {
  if (routes.length === 0) {
    return (
      <p className="text-center text-sm text-slate-500">경로 결과가 여기에 표시됩니다.</p>
    );
  }
  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {routes.map((r) => (
        <div
          key={r.id ?? `${r.engine}-${r.objective}`}
          onMouseEnter={() => onHover?.(r.id ?? null)}
          onMouseLeave={() => onHover?.(null)}
          className={clsx(
            "min-w-[200px] cursor-default rounded-lg border bg-white p-3 shadow-sm transition",
            r.is_recommended
              ? "border-eco-500 ring-2 ring-eco-200"
              : "border-slate-200 hover:border-slate-400",
          )}
        >
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-600">
              {ENGINE_LABEL[r.engine] ?? r.engine}
              {" / "}
              {OBJECTIVE_LABEL[r.objective] ?? r.objective}
            </span>
            {r.is_recommended && (
              <span className="rounded-full bg-eco-100 px-2 py-0.5 text-xs font-semibold text-eco-700">
                🌱 추천
              </span>
            )}
          </div>
          <div className="mt-2 space-y-0.5 text-sm">
            <div>
              <span className="text-slate-500">거리</span>{" "}
              <span className="font-semibold">{(r.total_distance_m / 1000).toFixed(1)} km</span>
            </div>
            <div>
              <span className="text-slate-500">시간</span>{" "}
              <span className="font-semibold">{Math.round(r.total_duration_s / 60)} 분</span>
            </div>
            <div>
              <span className="text-slate-500">CO₂</span>{" "}
              <span className="font-semibold">{Math.round(r.total_co2_g).toLocaleString()} g</span>
            </div>
          </div>
          {r.score !== null && r.score !== undefined && (
            <div className="mt-1.5 text-[10px] text-slate-400">
              score: {r.score.toFixed(3)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
