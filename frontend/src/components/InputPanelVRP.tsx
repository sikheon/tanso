"use client";

import { useState } from "react";

import VehicleSelector from "@/components/VehicleSelector";
import { api } from "@/lib/api";
import { useEloStore } from "@/store/useEloStore";

interface JobRow {
  label: string;
  lat: string;
  lng: string;
}

const PRESET_TEXT = `강남구청 차고지에서 출발해 송파 3곳, 강동 2곳 배송, 12시까지 복귀.
11톤 디젤 트럭이고 친환경 최우선으로 가야해.
송파 2번 고객은 점심시간 12-13시 받지 못함, 송파 1번은 후문 진입 필수.`;

const PRESET_JOBS: JobRow[] = [
  { label: "송파-1", lat: "37.5145", lng: "127.1066" },
  { label: "송파-2", lat: "37.5145", lng: "127.0866" },
  { label: "송파-3", lat: "37.5045", lng: "127.0966" },
  { label: "강동-1", lat: "37.5301", lng: "127.1238" },
  { label: "강동-2", lat: "37.5491", lng: "127.1380" },
];

export default function InputPanelVRP() {
  const [text, setText] = useState(PRESET_TEXT);
  const [parsing, setParsing] = useState(false);
  const [parsedWeights, setParsedWeights] = useState<{
    distance: number; duration: number; co2: number;
  } | null>(null);
  const [constraints, setConstraints] = useState<unknown[]>([]);
  const [depot, setDepot] = useState<JobRow>({
    label: "강남구청", lat: "37.5172", lng: "127.0473",
  });
  const [jobs, setJobs] = useState<JobRow[]>(PRESET_JOBS);

  const selectedVehicleId = useEloStore((s) => s.selectedVehicleId);
  const setCurrentRun = useEloStore((s) => s.setCurrentRun);
  const setLoading = useEloStore((s) => s.setLoading);
  const setError = useEloStore((s) => s.setError);
  const loadHistory = useEloStore((s) => s.loadHistory);
  const loading = useEloStore((s) => s.loading);

  async function parse() {
    setParsing(true);
    setError(null);
    try {
      const resp = await api.parse(text);
      if (resp.weights) {
        setParsedWeights(resp.weights);
      }
      if (resp.constraints) {
        setConstraints(resp.constraints);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setParsing(false);
    }
  }

  async function solve() {
    if (!selectedVehicleId) {
      setError("차량을 먼저 선택하세요");
      return;
    }
    const dlat = Number(depot.lat), dlng = Number(depot.lng);
    if (Number.isNaN(dlat) || Number.isNaN(dlng)) {
      setError("차고지 좌표가 올바르지 않습니다");
      return;
    }
    const jobsBody = jobs
      .map((j) => ({
        label: j.label || undefined,
        location: { lat: Number(j.lat), lng: Number(j.lng) },
      }))
      .filter((j) =>
        !Number.isNaN(j.location.lat) && !Number.isNaN(j.location.lng),
      );
    if (jobsBody.length === 0) {
      setError("배송지가 1개 이상 필요합니다");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const resp = await api.vrp({
        depot: { lat: dlat, lng: dlng, address: depot.label },
        jobs: jobsBody,
        vehicle_id: selectedVehicleId,
        options: {
          matrix_engine: "ors",
          objectives: ["distance", "duration", "co2"],
          solver_time_limit_s: 5,
          weights: parsedWeights ?? undefined,
        },
      });
      setCurrentRun({ kind: "vrp", payload: resp });
      await loadHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function updateJob(i: number, patch: Partial<JobRow>) {
    setJobs(jobs.map((j, idx) => (idx === i ? { ...j, ...patch } : j)));
  }

  return (
    <div className="space-y-4">
      <label className="block">
        <span className="mb-1 block text-sm font-medium text-slate-700">
          ✏️ 배송 요청 (자연어)
        </span>
        <textarea
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-eco-500 focus:outline-none focus:ring-1 focus:ring-eco-500"
        />
      </label>
      <button
        onClick={parse}
        disabled={parsing}
        className="w-full rounded-md border border-eco-300 bg-eco-50 px-4 py-2 text-sm font-semibold text-eco-700 transition hover:bg-eco-100 disabled:opacity-60"
      >
        {parsing ? "AI 분석 중..." : "🤖 AI 파싱 (가중치 + 제약 추출)"}
      </button>

      {parsedWeights && (
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs">
          <div className="mb-1 font-semibold text-slate-700">⚖ AI가 정한 가중치</div>
          <div className="grid grid-cols-3 gap-2">
            <Stat label="거리" value={parsedWeights.distance} />
            <Stat label="시간" value={parsedWeights.duration} />
            <Stat label="CO₂" value={parsedWeights.co2} accent />
          </div>
        </div>
      )}

      {constraints.length > 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs">
          <div className="mb-1 font-semibold text-amber-800">
            🚧 추출된 제약 ({constraints.length})
          </div>
          <ul className="list-disc space-y-0.5 pl-4 text-amber-900">
            {constraints.map((c, i) => (
              <li key={i}>{JSON.stringify(c)}</li>
            ))}
          </ul>
        </div>
      )}

      <details className="rounded-md border border-slate-200 bg-white p-3">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700">
          📍 차고지 + 배송지 좌표 ({jobs.length}개) — 편집 가능
        </summary>
        <div className="mt-2 space-y-2 text-xs">
          <JobInput
            row={depot}
            prefix="차고지"
            onChange={(patch) => setDepot({ ...depot, ...patch })}
          />
          {jobs.map((j, i) => (
            <JobInput
              key={i}
              row={j}
              prefix={`#${i + 1}`}
              onChange={(patch) => updateJob(i, patch)}
            />
          ))}
        </div>
      </details>

      <VehicleSelector />

      <button
        disabled={loading}
        onClick={solve}
        className="w-full rounded-md bg-eco-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-eco-700 disabled:cursor-wait disabled:opacity-60"
      >
        {loading ? "최적화 중..." : "🌱 최적 경로 계산"}
      </button>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className={`rounded ${accent ? "bg-eco-100" : "bg-white"} p-1.5 text-center`}>
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className={`text-sm font-semibold ${accent ? "text-eco-700" : "text-slate-700"}`}>
        {value.toFixed(2)}
      </div>
    </div>
  );
}

function JobInput({
  row, prefix, onChange,
}: {
  row: JobRow; prefix: string;
  onChange: (patch: Partial<JobRow>) => void;
}) {
  return (
    <div className="grid grid-cols-[60px_1fr_80px_80px] items-center gap-1">
      <span className="text-slate-500">{prefix}</span>
      <input
        type="text" value={row.label}
        onChange={(e) => onChange({ label: e.target.value })}
        className="rounded border border-slate-300 px-1.5 py-1"
      />
      <input
        type="number" step="0.0001" value={row.lat}
        onChange={(e) => onChange({ lat: e.target.value })}
        className="rounded border border-slate-300 px-1.5 py-1"
      />
      <input
        type="number" step="0.0001" value={row.lng}
        onChange={(e) => onChange({ lng: e.target.value })}
        className="rounded border border-slate-300 px-1.5 py-1"
      />
    </div>
  );
}
