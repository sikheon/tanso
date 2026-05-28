"use client";

import { useState } from "react";

import ReactMarkdown from "react-markdown";

interface Props {
  narrative?: string | null;
}

export default function NarrativePanel({ narrative }: Props) {
  const [copied, setCopied] = useState(false);

  if (!narrative) {
    return (
      <p className="text-sm italic text-slate-500">
        결과가 나오면 AI가 추천 사유를 자연어로 설명합니다.
      </p>
    );
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(narrative ?? "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  }

  return (
    <div className="rounded-lg border border-eco-200 bg-eco-50/60 p-4">
      <div className="prose prose-sm max-w-none prose-headings:mt-0 prose-headings:text-eco-700 prose-strong:text-eco-700">
        <ReactMarkdown>{narrative}</ReactMarkdown>
      </div>
      <div className="mt-2 flex items-center justify-end gap-2 text-xs">
        <button
          onClick={copy}
          className="rounded border border-slate-300 bg-white px-2 py-1 text-slate-600 hover:bg-slate-100"
        >
          {copied ? "복사됨!" : "📋 복사"}
        </button>
      </div>
    </div>
  );
}
