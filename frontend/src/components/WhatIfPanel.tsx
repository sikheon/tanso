"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useEloStore } from "@/store/useEloStore";

export default function WhatIfPanel({ runId }: { runId: number | null }) {
  const vehicles = useEloStore((s) => s.vehicles);
  const setCurrentRun = useEloStore((s) => s.setCurrentRun);
  const setError = useEloStore((s) => s.setError);
  const loadHistory = useEloStore((s) => s.loadHistory);
  const [pending, setPending] = useState<number | null>(null);

  if (runId == null) return null;

  async function recalc(vehicleId: number) {
    setPending(vehicleId);
    setError(null);
    try {
      const resp = await api.recalculate(runId!, { vehicle_id: vehicleId });
      setCurrentRun({ kind: "recalc", payload: resp, originalRunId: runId! });
      await loadHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="mb-2 text-sm font-semibold text-slate-700">
        🔄 What-if 차종 비교 (라우팅 재호출 없이)
      </div>
      <div className="flex flex-wrap gap-1.5">
        {vehicles.map((v) => (
          <button
            key={v.id}
            disabled={pending !== null}
            onClick={() => recalc(v.id)}
            className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 text-xs text-slate-700 hover:bg-eco-50 hover:text-eco-700 disabled:opacity-50"
          >
            {pending === v.id ? "..." : v.model ?? `#${v.id}`}
          </button>
        ))}
      </div>
    </div>
  );
}
