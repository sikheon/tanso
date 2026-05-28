"use client";

import { useEffect, useMemo, useState } from "react";

import HistorySidePanel from "@/components/HistorySidePanel";
import InputPanelP2P from "@/components/InputPanelP2P";
import InputPanelVRP from "@/components/InputPanelVRP";
import KakaoMap, { type KakaoMapMarker } from "@/components/KakaoMap";
import MapLegend from "@/components/MapLegend";
import NarrativePanel from "@/components/NarrativePanel";
import RouteCards from "@/components/RouteCards";
import SavingsBanner from "@/components/SavingsBanner";
import WhatIfPanel from "@/components/WhatIfPanel";
import { useEloStore } from "@/store/useEloStore";

export default function HomePage() {
  const mode = useEloStore((s) => s.mode);
  const setMode = useEloStore((s) => s.setMode);
  const currentRun = useEloStore((s) => s.currentRun);
  const loading = useEloStore((s) => s.loading);
  const error = useEloStore((s) => s.error);
  const setError = useEloStore((s) => s.setError);
  const loadVehicles = useEloStore((s) => s.loadVehicles);

  const [historyOpen, setHistoryOpen] = useState(false);
  const [hoveredRouteId, setHoveredRouteId] = useState<number | null>(null);

  useEffect(() => {
    void loadVehicles();
  }, [loadVehicles]);

  // Derive map markers + routes from currentRun
  const { markers, routes, runId } = useMemo(() => {
    if (!currentRun) return { markers: [], routes: [], runId: null as number | null };
    if (currentRun.kind === "p2p") {
      const p = currentRun.payload;
      const m: KakaoMapMarker[] = [];
      const rec = p.routes.find((r) => r.is_recommended) ?? p.routes[0];

      // Try parsed_request first (origin + destination + waypoints stored on Run)
      const parsed = (p as any).parsed_request ?? null;
      if (parsed?.origin) {
        m.push({
          position: { lat: parsed.origin.lat, lng: parsed.origin.lng },
          type: "origin",
          label: parsed.origin.address,
        });
      }
      // Waypoints in request body, ordered
      const wps = parsed?.waypoints ?? [];
      wps.forEach((w: any, i: number) => {
        m.push({
          position: { lat: w.lat, lng: w.lng },
          type: "waypoint",
          index: i + 1,
          label: w.address,
        });
      });
      if (parsed?.destination) {
        m.push({
          position: { lat: parsed.destination.lat, lng: parsed.destination.lng },
          type: "destination",
          label: parsed.destination.address,
        });
      }

      // Fallback: derive from first/last segment if parsed_request missing
      if (m.length === 0 && rec?.polyline?.length) {
        const first = rec.polyline[0];
        const last = rec.polyline[rec.polyline.length - 1];
        m.push({ position: { lat: first[0], lng: first[1] }, type: "origin" });
        m.push({ position: { lat: last[0], lng: last[1] }, type: "destination" });
      } else if (m.length === 0 && rec?.segments?.length) {
        const first = rec.segments[0];
        const last = rec.segments[rec.segments.length - 1];
        m.push({ position: { lat: first.from_lat, lng: first.from_lng }, type: "origin" });
        m.push({ position: { lat: last.to_lat, lng: last.to_lng }, type: "destination" });
      }
      return { markers: m, routes: p.routes, runId: p.run_id };
    }
    if (currentRun.kind === "vrp") {
      const p = currentRun.payload;
      const m: KakaoMapMarker[] = [
        { position: p.depot, type: "depot", label: "차고" },
        ...p.jobs.map((j, i) => ({
          position: j.location,
          type: "waypoint" as const,
          label: `${i + 1}.${j.label ?? ""}`,
        })),
      ];
      return { markers: m, routes: [], runId: p.run_id };
    }
    if (currentRun.kind === "recalc") {
      const p = currentRun.payload;
      const m: KakaoMapMarker[] = [];
      const rec = p.routes.find((r) => r.is_recommended) ?? p.routes[0];
      if (rec?.polyline?.length) {
        const first = rec.polyline[0];
        const last = rec.polyline[rec.polyline.length - 1];
        m.push({ position: { lat: first[0], lng: first[1] }, type: "origin" });
        m.push({ position: { lat: last[0], lng: last[1] }, type: "destination" });
      }
      return { markers: m, routes: p.routes, runId: p.new_run_id };
    }
    return { markers: [], routes: [], runId: null };
  }, [currentRun]);

  const narrative =
    currentRun?.kind === "p2p"
      ? currentRun.payload.narrative
      : currentRun?.kind === "recalc"
        ? currentRun.payload.narrative
        : currentRun?.kind === "vrp"
          ? currentRun.payload.narrative
          : null;

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
        <div>
          <h1 className="text-lg font-bold text-eco-700">E.L.O</h1>
          <p className="text-xs text-slate-500">친환경 물류 경로 추천</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setHistoryOpen(true)}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs hover:bg-slate-50"
          >
            📜 이력
          </button>
        </div>
      </header>

      {/* Mode toggle */}
      <div className="border-b border-slate-100 bg-slate-50 px-5 py-2">
        <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-xs">
          {(["p2p", "vrp"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-md px-3 py-1 ${
                mode === m
                  ? "bg-eco-600 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {m === "p2p" ? "P2P 폼" : "VRP 자연어"}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="flex items-center justify-between border-b border-rose-200 bg-rose-50 px-5 py-2 text-xs text-rose-700">
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)} className="text-rose-500">✕</button>
        </div>
      )}

      {/* Main split */}
      <div className="flex flex-1 overflow-hidden">
        {/* Input column */}
        <aside className="w-[380px] overflow-y-auto border-r border-slate-200 bg-white p-4">
          {mode === "p2p" ? <InputPanelP2P /> : <InputPanelVRP />}
        </aside>

        {/* Map column */}
        <main className="relative flex-1 bg-slate-100 p-3">
          <KakaoMap markers={markers} routes={routes} highlightRouteId={hoveredRouteId} />
          <MapLegend
            routes={routes.length ? routes : undefined}
            vrpResults={currentRun?.kind === "vrp" ? currentRun.payload.results : undefined}
            onHover={setHoveredRouteId}
          />
          {loading && (
            <div className="absolute left-1/2 top-4 -translate-x-1/2 rounded-full bg-white px-3 py-1 text-xs text-slate-600 shadow-md">
              ⏳ 분석 중...
            </div>
          )}
        </main>
      </div>

      {/* Bottom: cards + narrative + what-if */}
      <div className="grid grid-cols-1 gap-3 border-t border-slate-200 bg-white p-3 md:grid-cols-[2fr_1fr]">
        <div className="space-y-2">
          <SavingsBanner
            routes={
              currentRun?.kind === "p2p"
                ? currentRun.payload.routes
                : currentRun?.kind === "recalc"
                  ? currentRun.payload.routes
                  : undefined
            }
            vrpResults={currentRun?.kind === "vrp" ? currentRun.payload.results : undefined}
            vehicleLabel={
              currentRun?.kind === "p2p"
                ? currentRun.payload.vehicle?.model ?? undefined
                : currentRun?.kind === "vrp"
                  ? currentRun.payload.vehicle?.model ?? undefined
                  : currentRun?.kind === "recalc"
                    ? currentRun.payload.vehicle?.model ?? undefined
                    : undefined
            }
          />
          <RouteCards
            routes={
              currentRun?.kind === "p2p"
                ? currentRun.payload.routes
                : currentRun?.kind === "recalc"
                  ? currentRun.payload.routes
                  : []
            }
            onHover={setHoveredRouteId}
          />
          {currentRun?.kind === "vrp" && (
            <div className="flex gap-3 overflow-x-auto">
              {currentRun.payload.results.map((r) => (
                <div
                  key={r.objective}
                  className={`min-w-[200px] rounded-lg border p-3 shadow-sm ${
                    r.is_recommended
                      ? "border-eco-500 ring-2 ring-eco-200"
                      : "border-slate-200"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-600">
                      {r.objective === "co2" ? "CO₂ 최소" : r.objective === "duration" ? "시간 최소" : "거리 최소"}
                    </span>
                    {r.is_recommended && (
                      <span className="rounded-full bg-eco-100 px-2 py-0.5 text-xs font-semibold text-eco-700">
                        🌱
                      </span>
                    )}
                  </div>
                  <div className="mt-2 text-sm">
                    {(r.total_distance_m / 1000).toFixed(1)} km / {Math.round(r.total_duration_s / 60)} min
                    <div className="font-semibold">
                      {Math.round(r.total_co2_g).toLocaleString()} g CO₂
                    </div>
                  </div>
                  <div className="mt-1 text-[10px] text-slate-400">{r.solve_ms} ms</div>
                </div>
              ))}
            </div>
          )}
          <WhatIfPanel runId={runId} />
        </div>
        <NarrativePanel narrative={narrative} />
      </div>

      <HistorySidePanel open={historyOpen} onClose={() => setHistoryOpen(false)} />
    </div>
  );
}
