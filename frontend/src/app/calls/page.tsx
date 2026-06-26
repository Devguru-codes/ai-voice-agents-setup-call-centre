"use client";

import { useEffect, useState } from "react";
import { listCalls } from "@/lib/api";
import type { CallSummary } from "@/lib/api";
import Link from "next/link";

function SentimentBadge({ s }: { s: string | null }) {
  const styles: Record<string, string> = {
    positive: "bg-green-900/40 text-green-400",
    neutral:  "bg-gray-800 text-gray-400",
    negative: "bg-red-900/40 text-red-400",
  };
  const key = s || "neutral";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[key] || styles.neutral} capitalize`}>
      {key}
    </span>
  );
}

export default function CallsPage() {
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const PAGE_SIZE = 20;

  useEffect(() => {
    setLoading(true);
    listCalls(page, PAGE_SIZE)
      .then((data) => { setCalls(data.calls); setTotal(data.total); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-6 fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">All Calls</h1>
          <p className="text-gray-500 text-sm">{total} total calls</p>
        </div>
        <Link
          href="/call"
          className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
        >
          🎙️ New Call
        </Link>
      </div>

      {error && (
        <div className="card border-red-800 bg-red-900/10">
          <p className="text-red-400 text-sm">⚠️ {error}</p>
        </div>
      )}

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-gray-800">
            <tr className="text-gray-500 text-xs uppercase tracking-wide">
              <th className="text-left p-4">Date / Time</th>
              <th className="text-left p-4">Duration</th>
              <th className="text-left p-4">Agent</th>
              <th className="text-left p-4">Sentiment</th>
              <th className="text-left p-4">Score</th>
              <th className="text-left p-4">Summary</th>
              <th className="text-left p-4"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="text-center py-16 text-gray-600">
                  Loading...
                </td>
              </tr>
            ) : calls.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-16 text-gray-600">
                  No calls yet.{" "}
                  <Link href="/call" className="text-brand-400 hover:underline">
                    Start one →
                  </Link>
                </td>
              </tr>
            ) : (
              calls.map((call) => (
                <tr
                  key={call.id}
                  className="border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors"
                >
                  <td className="p-4 text-gray-400 whitespace-nowrap">
                    {call.started_at
                      ? new Date(call.started_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="p-4 text-gray-400">
                    {call.duration_seconds != null
                      ? `${Math.floor(call.duration_seconds / 60)}m ${Math.round(call.duration_seconds % 60)}s`
                      : "—"}
                  </td>
                  <td className="p-4">
                    <span className="px-2 py-0.5 bg-gray-800 rounded text-xs text-gray-300 capitalize">
                      {call.agent_used || "—"}
                    </span>
                  </td>
                  <td className="p-4">
                    <SentimentBadge s={call.sentiment} />
                  </td>
                  <td className="p-4">
                    {call.lead_score != null ? (
                      <span
                        className={`font-bold ${
                          call.lead_score >= 7
                            ? "text-green-400"
                            : call.lead_score >= 4
                            ? "text-yellow-400"
                            : "text-red-400"
                        }`}
                      >
                        {call.lead_score}/10
                      </span>
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
                  </td>
                  <td className="p-4 text-gray-500 text-xs max-w-xs truncate">
                    {call.summary || "—"}
                  </td>
                  <td className="p-4">
                    <Link
                      href={`/calls/${call.id}`}
                      className="text-brand-400 hover:text-brand-300 text-xs"
                    >
                      View →
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between p-4 border-t border-gray-800">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 text-xs text-gray-400 hover:text-white disabled:opacity-30 transition-colors"
            >
              ← Prev
            </button>
            <span className="text-xs text-gray-600">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 text-xs text-gray-400 hover:text-white disabled:opacity-30 transition-colors"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
