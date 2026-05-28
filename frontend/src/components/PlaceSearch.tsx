"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { GeocodeItem } from "@/lib/types";

interface Props {
  placeholder?: string;
  onPick: (item: GeocodeItem) => void;
}

export default function PlaceSearch({ placeholder = "주소·장소 검색", onPick }: Props) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<GeocodeItem[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!query || query.trim().length < 2) {
      setItems([]);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      setLoading(true);
      setError(null);
      try {
        const res = await api.geocode(query, 8);
        setItems(res.items);
        setOpen(true);
      } catch (e) {
        if (!(e instanceof Error && e.name === "AbortError")) {
          setError(e instanceof Error ? e.message : String(e));
          setItems([]);
        }
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function handlePick(item: GeocodeItem) {
    onPick(item);
    setQuery("");
    setItems([]);
    setOpen(false);
  }

  return (
    <div ref={wrapperRef} className="relative">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => items.length > 0 && setOpen(true)}
          placeholder={placeholder}
          className="w-full rounded-md border border-slate-300 px-3 py-1.5 pl-8 text-sm focus:border-eco-500 focus:outline-none focus:ring-1 focus:ring-eco-500"
        />
        <span className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400">
          {loading ? "⏳" : "🔍"}
        </span>
        {query && (
          <button
            onClick={() => {
              setQuery("");
              setItems([]);
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-600"
          >
            ✕
          </button>
        )}
      </div>
      {error && (
        <div className="mt-1 text-xs text-rose-600">{error}</div>
      )}
      {open && items.length > 0 && (
        <ul className="absolute z-[2000] mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
          {items.map((it, i) => (
            <li
              key={`${it.lat},${it.lng}-${i}`}
              onClick={() => handlePick(it)}
              className="cursor-pointer border-b border-slate-100 px-3 py-2 text-xs hover:bg-eco-50 last:border-0"
            >
              <div className="font-semibold text-slate-800">{it.name}</div>
              <div className="text-slate-500">{it.address}</div>
              {it.category && (
                <div className="mt-0.5 text-[10px] text-slate-400">{it.category}</div>
              )}
            </li>
          ))}
        </ul>
      )}
      {open && !loading && items.length === 0 && query.trim().length >= 2 && (
        <div className="absolute z-[2000] mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500 shadow">
          검색 결과 없음
        </div>
      )}
    </div>
  );
}
