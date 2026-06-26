"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from "recharts";
import { getAnalyticsSummary, listCalls } from "@/lib/api";
import type { CallSummary } from "@/lib/api";
import Link from "next/link";

const SENTIMENT_COLORS: Record<string, string> = {
  positive: "#22c55e",
  neutral:  "#94a3b8",
  negative: "#ef4444",
};

interface KPICardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon: string;
}

function KPICard({ label, value, sub, icon }: KPICardProps) {
  return (
    <div className="card fade-in">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-gray-500 text-xs font-medium uppercase tracking-wide">{label}</p>
          <p className="text-3xl font-bold text-white mt-1">{value}</p>
          {sub && <p className="text-gray-500 text-xs mt-1">{sub}</p>}
        </div>
        <span className="text-2xl">{icon}</span>
      </div>
    </div>
  );
}

function SentimentBadge({ sentiment }: { sentiment: string | null }) {
  const map: Record<string, string> = {
    positive: "bg-green-900/40 text-green-400",
    neutral:  "bg-gray-800 text-gray-400",
    negative: "bg-red-900/40 text-red-400",
  };
  const s = sentiment || "neutral";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[s] || map.neutral}`}>
      {s}
    </span>
  );
}

function LeadScore({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-600">—</span>;
  const color = score >= 7 ? "text-green-400" : score >= 4 ? "text-yellow-400" : "text-red-400";
  return <span className={`font-bold ${color}`}>{score}/10</span>;
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<any>(null);
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [s, c] = await Promise.all([
          getAnalyticsSummary(),
          listCalls(1, 5),
        ]);
        setSummary(s);
        setCalls(c.calls);
      } catch (e: any) {
        setError(e.message || "Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin text-4xl">⚙️</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card border-red-800 bg-red-900/10">
        <p className="text-red-400 font-medium">⚠️ {error}</p>
        <p className="text-gray-500 text-sm mt-1">
          Make sure the backend is running on{" "}
          <code className="font-mono text-gray-400">http://localhost:8000</code>
        </p>
      </div>
    );
  }

  const pieData = Object.entries(summary?.sentiment || {}).map(([name, value]) => ({
    name,
    value: value as number,
  }));

  return (
    <div className="space-y-8 fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-0.5">Real-time performance overview</p>
        </div>
        <Link
          href="/call"
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
        >
          🎙️ Start New Call
        </Link>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Total Calls"
          value={summary?.total_calls ?? 0}
          icon="📞"
        />
        <KPICard
          label="Avg Duration"
          value={summary?.avg_duration_seconds
            ? `${Math.floor(summary.avg_duration_seconds / 60)}m ${Math.round(summary.avg_duration_seconds % 60)}s`
            : "—"}
          icon="⏱️"
        />
        <KPICard
          label="Avg Lead Score"
          value={summary?.avg_lead_score ? `${summary.avg_lead_score.toFixed(1)}/10` : "—"}
          icon="⭐"
        />
        <KPICard
          label="Positive Calls"
          value={summary?.sentiment?.positive ?? 0}
          sub={`of ${summary?.total_calls ?? 0} total`}
          icon="😊"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Call trend */}
        <div className="card lg:col-span-2">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">📈 Calls — Last 7 Days</h2>
          {summary?.trend?.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={summary.trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 11 }} />
                <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "#111827", border: "1px solid #374151" }}
                  labelStyle={{ color: "#9ca3af" }}
                />
                <Line
                  type="monotone"
                  dataKey="calls"
                  stroke="#5c7cfa"
                  strokeWidth={2}
                  dot={{ fill: "#5c7cfa", r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-600 text-sm py-12 text-center">No data yet</p>
          )}
        </div>

        {/* Sentiment pie */}
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">🎭 Sentiment</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                >
                  {pieData.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={SENTIMENT_COLORS[entry.name] || "#6b7280"}
                    />
                  ))}
                </Pie>
                <Legend
                  formatter={(v) => (
                    <span className="text-xs text-gray-400 capitalize">{v}</span>
                  )}
                />
                <Tooltip
                  contentStyle={{ background: "#111827", border: "1px solid #374151" }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-600 text-sm py-12 text-center">No data yet</p>
          )}
        </div>
      </div>

      {/* Recent calls table */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300">📋 Recent Calls</h2>
          <Link href="/calls" className="text-brand-400 text-xs hover:text-brand-300">
            View all →
          </Link>
        </div>
        {calls.length === 0 ? (
          <p className="text-gray-600 text-sm text-center py-8">
            No calls yet. <Link href="/call" className="text-brand-400">Start a call →</Link>
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-600 text-xs uppercase tracking-wide border-b border-gray-800">
                <th className="text-left py-2 pr-4">Time</th>
                <th className="text-left py-2 pr-4">Duration</th>
                <th className="text-left py-2 pr-4">Agent</th>
                <th className="text-left py-2 pr-4">Sentiment</th>
                <th className="text-left py-2 pr-4">Score</th>
                <th className="text-left py-2">Summary</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((call) => (
                <tr
                  key={call.id}
                  className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
                >
                  <td className="py-3 pr-4 text-gray-400 whitespace-nowrap">
                    <Link href={`/calls/${call.id}`} className="hover:text-brand-400">
                      {call.started_at
                        ? new Date(call.started_at).toLocaleTimeString()
                        : "—"}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 text-gray-400">
                    {call.duration_seconds
                      ? `${Math.floor(call.duration_seconds / 60)}m ${Math.round(call.duration_seconds % 60)}s`
                      : "—"}
                  </td>
                  <td className="py-3 pr-4">
                    <span className="px-2 py-0.5 bg-gray-800 rounded text-xs text-gray-300 capitalize">
                      {call.agent_used || "—"}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <SentimentBadge sentiment={call.sentiment} />
                  </td>
                  <td className="py-3 pr-4">
                    <LeadScore score={call.lead_score} />
                  </td>
                  <td className="py-3 text-gray-500 text-xs max-w-xs truncate">
                    {call.summary || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
