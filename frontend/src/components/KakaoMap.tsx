"use client";

// Map powered by Leaflet + OpenStreetMap.
// Filename kept as KakaoMap.tsx so all importing pages stay unchanged.

import "leaflet/dist/leaflet.css";

import { useEffect, useRef, useState } from "react";

import type { LatLng, Route } from "@/lib/types";

export interface KakaoMapMarker {
  position: LatLng;
  label?: string;
  type?: "origin" | "destination" | "waypoint" | "depot";
  index?: number;
}

interface KakaoMapProps {
  markers?: KakaoMapMarker[];
  routes?: Route[];
  highlightRouteId?: number | null;
  center?: LatLng;
  zoom?: number;
}

const ROUTE_COLORS: Record<string, string> = {
  kakao: "#3b82f6",
  ors: "#a855f7",
  or_tools_vrp: "#10b981",
};

const MARKER_LABELS: Record<NonNullable<KakaoMapMarker["type"]>, string> = {
  origin: "출발",
  destination: "도착",
  waypoint: "경유",
  depot: "차고",
};

const MARKER_STYLES: Record<
  NonNullable<KakaoMapMarker["type"]>,
  { bg: string; ring: string; size: number; emoji: string }
> = {
  origin:      { bg: "#10b981", ring: "#065f46", size: 30, emoji: "🚩" },
  destination: { bg: "#ef4444", ring: "#7f1d1d", size: 30, emoji: "🏁" },
  waypoint:    { bg: "#f59e0b", ring: "#78350f", size: 24, emoji: "" },
  depot:       { bg: "#6366f1", ring: "#312e81", size: 30, emoji: "🏠" },
};

function buildIconHtml(
  type: NonNullable<KakaoMapMarker["type"]>,
  index?: number,
): string {
  const s = MARKER_STYLES[type];
  const inside =
    type === "waypoint" && typeof index === "number" ? String(index) : s.emoji;
  return `
    <div style="
      width:${s.size}px; height:${s.size}px;
      border-radius:50%;
      background:${s.bg};
      border:3px solid white;
      box-shadow:0 0 0 2px ${s.ring}, 0 2px 6px rgba(0,0,0,0.35);
      display:flex; align-items:center; justify-content:center;
      color:white; font-weight:700;
      font-size:${type === "waypoint" ? "12px" : "15px"};
      line-height:1;">${inside}</div>`;
}

export default function KakaoMap({
  markers = [],
  routes = [],
  highlightRouteId = null,
  center = { lat: 36.5, lng: 127.8 },
  zoom = 7,
}: KakaoMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const layersRef = useRef<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !containerRef.current) return;
    // Strict-mode / hot-reload guard: don't re-init if already attached.
    if (mapRef.current) return;
    if ((containerRef.current as any)._leaflet_id) return;
    let cancelled = false;

    import("leaflet")
      .then((mod) => {
        const L = (mod as any).default ?? mod;
        if (cancelled || !containerRef.current) return;
        // Re-check after async import — another mount might have raced us.
        if ((containerRef.current as any)._leaflet_id) return;

        delete (L.Icon.Default.prototype as any)._getIconUrl;
        L.Icon.Default.mergeOptions({
          iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
          iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
          shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
        });

        const map = L.map(containerRef.current, {
          center: [center.lat, center.lng],
          zoom,
          zoomControl: true,
        });
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);
        mapRef.current = map;
        // Resize-trigger to handle hidden-on-mount cases
        setTimeout(() => map.invalidateSize(), 0);
      })
      .catch((e) => {
        console.error("[Map] Leaflet load failed", e);
        setError(e instanceof Error ? e.message : String(e));
      });

    return () => {
      cancelled = true;
      if (mapRef.current) {
        try {
          mapRef.current.remove();
        } catch {
          // ignore
        }
        mapRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const map = mapRef.current;
    if (!map) return;
    let cancelled = false;

    import("leaflet").then((mod) => {
      if (cancelled || !mapRef.current) return;
      const L = (mod as any).default ?? mod;

      // Clear previous overlay layers — runs *inside* the async block so we
      // never race with a stale promise that still wants to add layers.
      layersRef.current.forEach((layer) => {
        try {
          map.removeLayer(layer);
        } catch {
          // ignore
        }
      });
      layersRef.current = [];

      const allPoints: [number, number][] = [];

      for (const r of routes) {
        if (!r.polyline || r.polyline.length === 0) continue;
        const isHighlight =
          highlightRouteId == null ? r.is_recommended : r.id === highlightRouteId;
        const polyline = L.polyline(r.polyline, {
          color: ROUTE_COLORS[r.engine] || "#64748b",
          weight: isHighlight ? 6 : 3,
          opacity: isHighlight ? 0.95 : 0.55,
        }).addTo(map);
        layersRef.current.push(polyline);
        for (const pt of r.polyline) allPoints.push(pt);
      }

      for (const m of markers) {
        const type = m.type ?? "waypoint";
        const style = MARKER_STYLES[type];
        const icon = L.divIcon({
          className: "elo-circle-marker",
          html: buildIconHtml(type, m.index),
          iconSize: [style.size, style.size],
          iconAnchor: [style.size / 2, style.size / 2],
        });
        const marker = L.marker([m.position.lat, m.position.lng], {
          icon,
          zIndexOffset:
            type === "origin" || type === "destination" ? 1000 : 500,
        }).addTo(map);
        layersRef.current.push(marker);
        const labelText = m.label ? m.label : MARKER_LABELS[type];
        if (labelText) {
          marker.bindTooltip(labelText, {
            permanent: true,
            direction: "top",
            offset: [0, -(style.size / 2 + 4)],
            className: "elo-marker-label",
          });
        }
        allPoints.push([m.position.lat, m.position.lng]);
      }

      if (allPoints.length > 0) {
        const bounds = L.latLngBounds(allPoints);
        map.fitBounds(bounds, { padding: [40, 40] });
      }
    });

    return () => {
      cancelled = true;
    };
  }, [markers, routes, highlightRouteId]);

  if (error) {
    return (
      <div className="flex h-full w-full items-center justify-center rounded-lg border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
        <div className="text-center">
          <div className="mb-2 text-3xl">🗺️</div>
          <div className="font-semibold">지도 로드 실패</div>
          <div className="mt-1 text-xs">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div ref={containerRef} className="h-full w-full rounded-lg" />
      <style jsx global>{`
        .elo-marker-label {
          background: white !important;
          border: 1px solid #cbd5e1 !important;
          border-radius: 4px !important;
          padding: 2px 6px !important;
          color: #334155 !important;
          font-weight: 600 !important;
          font-size: 11px !important;
          box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08) !important;
        }
        .elo-marker-label::before {
          display: none !important;
        }
        .elo-circle-marker {
          background: transparent !important;
          border: none !important;
        }
        .leaflet-container {
          background: #e2e8f0;
        }
      `}</style>
    </>
  );
}
