const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "APIError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail || detail;
    } catch {}
    throw new APIError(res.status, detail);
  }
  return res.json();
}

// ── Call token ────────────────────────────────────────────────────────────────
export async function getCallToken(customerId?: string) {
  return request<{ token: string; room_name: string; livekit_url: string }>(
    "/api/calls/token",
    {
      method: "POST",
      body: JSON.stringify({ customer_id: customerId }),
    }
  );
}

// ── Analytics ─────────────────────────────────────────────────────────────────
export async function getAnalyticsSummary() {
  return request<{
    total_calls: number;
    avg_duration_seconds: number;
    avg_lead_score: number;
    sentiment: Record<string, number>;
    trend: { date: string; calls: number }[];
  }>("/api/analytics/summary");
}

// ── Calls ─────────────────────────────────────────────────────────────────────
export async function listCalls(page = 1, pageSize = 20) {
  return request<{
    total: number;
    page: number;
    page_size: number;
    calls: CallSummary[];
  }>(`/api/calls?page=${page}&page_size=${pageSize}`);
}

export async function getCall(callId: string) {
  return request<CallDetail>(`/api/calls/${callId}`);
}

// ── Knowledge base ────────────────────────────────────────────────────────────
export async function uploadKnowledge(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/knowledge/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new APIError(res.status, err.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function ingestUrl(url: string) {
  const form = new FormData();
  form.append("url", url);
  const res = await fetch(`${API_BASE}/api/knowledge/url`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new APIError(res.status, "URL ingestion failed");
  return res.json();
}

export async function getKnowledgeSources() {
  return request<{ sources: { source: string }[] }>("/api/knowledge/sources");
}

export async function deleteSource(source: string) {
  return request<{ deleted_chunks: number }>(`/api/knowledge/sources/${encodeURIComponent(source)}`, {
    method: "DELETE",
  });
}

// ── Settings ──────────────────────────────────────────────────────────────────
export async function getSettings() {
  return request<AgentSettings>("/api/settings");
}

export async function updateSettings(data: Partial<AgentSettings>) {
  return request<{ message: string }>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface CallSummary {
  id: string;
  started_at: string | null;
  duration_seconds: number | null;
  sentiment: "positive" | "neutral" | "negative" | null;
  lead_score: number | null;
  agent_used: string | null;
  summary: string | null;
  customer_id: string | null;
}

export interface CallDetail extends CallSummary {
  ended_at: string | null;
  transcript: string | null;
  action_items: string[];
}

export interface AgentSettings {
  company_name: string;
  greeting: string;
  business_hours: string;
  escalation_email: string | null;
  voice_id: string;
}
