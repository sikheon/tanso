"use client";

import { create } from "zustand";

import { api } from "@/lib/api";
import type {
  P2PResponse,
  RecalculateResponse,
  RunListItem,
  VRPResponse,
  VehicleResponse,
} from "@/lib/types";

type Mode = "p2p" | "vrp";

export type CurrentRun =
  | { kind: "p2p"; payload: P2PResponse }
  | { kind: "vrp"; payload: VRPResponse }
  | { kind: "recalc"; payload: RecalculateResponse; originalRunId: number }
  | null;

interface EloState {
  mode: Mode;
  vehicles: VehicleResponse[];
  selectedVehicleId: number | null;
  currentRun: CurrentRun;
  history: RunListItem[];
  loading: boolean;
  error: string | null;

  setMode: (mode: Mode) => void;
  setVehicleId: (id: number) => void;
  loadVehicles: () => Promise<void>;
  loadHistory: () => Promise<void>;
  setCurrentRun: (run: CurrentRun) => void;
  clearCurrentRun: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  deleteRun: (runId: number) => Promise<void>;
}

export const useEloStore = create<EloState>((set, get) => ({
  mode: "p2p",
  vehicles: [],
  selectedVehicleId: null,
  currentRun: null,
  history: [],
  loading: false,
  error: null,

  setMode: (mode) => set({ mode }),
  setVehicleId: (selectedVehicleId) => set({ selectedVehicleId }),

  loadVehicles: async () => {
    try {
      const vehicles = await api.listVehicles();
      const currentId = get().selectedVehicleId;
      set({
        vehicles,
        selectedVehicleId:
          currentId && vehicles.some((v) => v.id === currentId)
            ? currentId
            : vehicles[0]?.id ?? null,
      });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    }
  },

  loadHistory: async () => {
    try {
      const res = await api.listRuns({ limit: 50 });
      set({ history: res.items });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    }
  },

  setCurrentRun: (currentRun) => set({ currentRun }),
  clearCurrentRun: () => set({ currentRun: null }),

  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  deleteRun: async (runId) => {
    await api.deleteRun(runId);
    set({ history: get().history.filter((h) => h.id !== runId) });
  },
}));
