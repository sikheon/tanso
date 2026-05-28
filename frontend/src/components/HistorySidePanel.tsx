"use client";

import { useEffect } from "react";

import { api } from "@/lib/api";
import { useEloStore } from "@/store/useEloStore";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function HistorySidePanel({ open, onClose }: Props) {
  const history = useEloStore((s) => s.history);
  const loadHistory = useEloStore((s) => s.loadHistory);
  const deleteRun = useEloStore((s) => s.deleteRun);
  const setCurrentRun = useEloStore((s) => s.setCurrentRun);
  const setError = useEloStore((s) => s.setError);

  useEffect(() => {
    if (open) {
      void loadHistory();
    }
  }, [open, loadHistory]);

  async function replay(runId: number) {
    try {
      const detail = await api.getRun(runId);
      // Wrap as P2P or VRP synthetic response so map/cards render
      const synthetic = {
        run_id: detail.id,
        status: detail.status as "done",
        mode: detail.mode,
        vehicle: detail.vehicle_snapshot!,
        weights: detail.weights ?? { distance: 1 / 3, duration: 1 / 3, co2: 1 / 3 },
        routes: detail.routes,
        narrative: detail.narrative,
        warnings: [],
        created_at: detail.created_at,
      };
      if (detail.mode === "p2p") {
        setCurrentRun({ kind: "p2p", payload: synthetic as never });
      } else {
        setCurrentRun({ kind: "vrp", payload: synthetic as never });
      }
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/30 transition"
        />
      )}
      {/* Panel */}
      <aside
        className={`fixed inset-y-0 right-0 z-40 w-96 transform overflow-y-auto bg-white shadow-xl transition-transform ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-700">📜 최근 실행</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-700">
            ✕
          </button>
        </div>

        <div className="space-y-2 p-3">
          {history.length === 0 && (
            <p className="py-8 text-center text-sm text-slate-400">
              실행 이력이 없습니다.
            </p>
          )}
          {history.map((h) => (
            <div
              key={h.id}
              className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 text-xs"
            >
              <div className="mb-1 flex items-center justify-between">
                <span className="font-mono text-slate-500">#{h.id}</span>
                <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
                  {h.mode.toUpperCase()}
                </span>
              </div>
              <div className="font-semibold text-slate-700">
                {h.vehicle?.model ?? `vehicle #${h.vehicle?.id ?? "?"}`}
                {h.label && <span className="ml-1 text-slate-500">— {h.label}</span>}
              </div>
              {h.summary && (
                <div className="mt-1 text-slate-600">
                  {h.summary.distance_km.toFixed(1)}km · {h.summary.duration_min}min ·{" "}
                  <span className="font-semibold text-eco-700">
                    {Math.round(h.summary.co2_g).toLocaleString()}g CO₂
                  </span>
                </div>
              )}
              <div className="mt-1 text-[10px] text-slate-400">
                {new Date(h.created_at).toLocaleString("ko-KR")}
              </div>
              <div className="mt-2 flex gap-1">
                <button
                  onClick={() => replay(h.id)}
                  className="rounded border border-slate-300 bg-white px-2 py-0.5 text-[11px] hover:bg-slate-100"
                >
                  재생
                </button>
                <button
                  onClick={() => void deleteRun(h.id)}
                  className="rounded border border-rose-300 bg-rose-50 px-2 py-0.5 text-[11px] text-rose-700 hover:bg-rose-100"
                >
                  삭제
                </button>
              </div>
            </div>
          ))}
        </div>
      </aside>
    </>
  );
}
