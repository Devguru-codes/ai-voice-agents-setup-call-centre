"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getCall } from "@/lib/api";
import type { CallDetail } from "@/lib/api";
import Link from "next/link";

const SENTIMENT_STYLES: Record<string, string> = {
  positive: "bg-green-900/30 text-green-400 border-green-800",
  neutral:  "bg-gray-800 text-gray-400 border-gray-700",
  negative: "bg-red-900/30 text-red-400 border-red-800",
};

export default function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [call, setCall] = useState<CallDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getCall(id)
      .then(setCall)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="text-gray-500 py-16 text-center">Loading...</div>;

  if (error || !call) {
    return (
      <div className="card border-red-800 bg-red-900/10">
        <p className="text-red-400">⚠️ {error || "Call not found"}</p>
        <Link href="/calls" className="text-brand-400 text-sm mt-2 inline-block">← Back</Link>
      </div>
    );
  }

  const duration = call.duration_seconds != null
    ? `${Math.floor(call.duration_seconds / 60)}m ${Math.round(call.duration_seconds % 60)}s`
    : "—";

  return (
    <div className="space-y-6 fade-in max-w-3xl">
      <div className="flex items-center gap-4">
        <Link href="/calls" className="text-gray-500 hover:text-white text-sm">← Calls</Link>
        <h1 className="text-xl font-bold text-white">Call Detail</h1>
      </div>

      {/* Meta grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <p className="text-xs text-gray-500 uppercase">Date</p>
          <p className="text-sm text-white mt-1">
            {call.started_at ? new Date(call.started_at).toLocaleString() : "—"}
          </p>
        </div>
        <div className="card">
          <p className="text-xs text-gray-500 uppercase">Duration</p>
          <p className="text-sm text-white mt-1">{duration}</p>
        </div>
        <div className="card">
          <p className="text-xs text-gray-500 uppercase">Agent</p>
          <p className="text-sm text-white mt-1 capitalize">{call.agent_used || "—"}</p>
        </div>
        <div className="card">
          <p className="text-xs text-gray-500 uppercase">Lead Score</p>
          <p className={`text-2xl font-bold mt-1 ${
            call.lead_score != null
              ? call.lead_score >= 7 ? "text-green-400" : call.lead_score >= 4 ? "text-yellow-400" : "text-red-400"
              : "text-gray-600"
          }`}>
            {call.lead_score != null ? `${call.lead_score}/10` : "—"}
          </p>
        </div>
      </div>

      {/* Sentiment + Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className={`card border rounded-xl ${SENTIMENT_STYLES[call.sentiment || "neutral"]}`}>
          <p className="text-xs uppercase font-medium opacity-70">Sentiment</p>
          <p className="text-lg font-bold mt-1 capitalize">{call.sentiment || "—"}</p>
        </div>
        <div className="card md:col-span-2">
          <p className="text-xs text-gray-500 uppercase mb-2">AI Summary</p>
          <p className="text-gray-300 text-sm leading-relaxed">{call.summary || "No summary available."}</p>
        </div>
      </div>

      {/* Action items */}
      {call.action_items?.length > 0 && (
        <div className="card">
          <p className="text-xs text-gray-500 uppercase mb-3">📋 Action Items</p>
          <ul className="space-y-2">
            {call.action_items.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                <span className="text-brand-400 mt-0.5">▸</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Transcript */}
      {call.transcript && (
        <div className="card">
          <p className="text-xs text-gray-500 uppercase mb-3">📝 Full Transcript</p>
          <pre className="whitespace-pre-wrap text-sm text-gray-400 font-mono leading-relaxed max-h-96 overflow-y-auto">
            {call.transcript}
          </pre>
        </div>
      )}
    </div>
  );
}
