"use client";

import { useEffect, useState, useRef } from "react";
import {
  getSettings, updateSettings, getKnowledgeSources,
  uploadKnowledge, ingestUrl, deleteSource,
} from "@/lib/api";
import type { AgentSettings } from "@/lib/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState<AgentSettings | null>(null);
  const [sources, setSources] = useState<{ source: string }[]>([]);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const showMsg = (type: "ok" | "err", text: string) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 4000);
  };

  useEffect(() => {
    Promise.all([getSettings(), getKnowledgeSources()])
      .then(([s, k]) => { setSettings(s); setSources(k.sources); })
      .catch((e) => showMsg("err", e.message));
  }, []);

  const handleSaveSettings = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      await updateSettings(settings);
      showMsg("ok", "Settings saved!");
    } catch (e: any) {
      showMsg("err", e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await uploadKnowledge(file);
      showMsg("ok", `'${file.name}' queued for ingestion.`);
      const k = await getKnowledgeSources();
      setSources(k.sources);
    } catch (ex: any) {
      showMsg("err", ex.message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleUrlIngest = async () => {
    if (!urlInput.trim()) return;
    setUploading(true);
    try {
      await ingestUrl(urlInput.trim());
      showMsg("ok", "URL queued for ingestion.");
      setUrlInput("");
      const k = await getKnowledgeSources();
      setSources(k.sources);
    } catch (ex: any) {
      showMsg("err", ex.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteSource = async (source: string) => {
    try {
      await deleteSource(source);
      setSources((prev) => prev.filter((s) => s.source !== source));
      showMsg("ok", `Deleted: ${source}`);
    } catch (e: any) {
      showMsg("err", e.message);
    }
  };

  return (
    <div className="max-w-2xl space-y-8 fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-gray-500 text-sm mt-0.5">Configure your AI agent and knowledge base</p>
      </div>

      {msg && (
        <div className={`card border text-sm font-medium ${
          msg.type === "ok"
            ? "border-green-800 bg-green-900/10 text-green-400"
            : "border-red-800 bg-red-900/10 text-red-400"
        }`}>
          {msg.type === "ok" ? "✅" : "⚠️"} {msg.text}
        </div>
      )}

      {/* Agent config */}
      {settings && (
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-gray-300">🤖 Agent Configuration</h2>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Company Name</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-500"
              value={settings.company_name}
              onChange={(e) => setSettings({ ...settings, company_name: e.target.value })}
            />
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Greeting Message</label>
            <textarea
              rows={3}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-500 resize-none"
              value={settings.greeting}
              onChange={(e) => setSettings({ ...settings, greeting: e.target.value })}
            />
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Business Hours</label>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-500"
              value={settings.business_hours}
              onChange={(e) => setSettings({ ...settings, business_hours: e.target.value })}
            />
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Escalation Email</label>
            <input
              type="email"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-500"
              value={settings.escalation_email || ""}
              placeholder="escalation@company.com"
              onChange={(e) => setSettings({ ...settings, escalation_email: e.target.value })}
            />
          </div>

          <button
            onClick={handleSaveSettings}
            disabled={saving}
            className="bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-semibold transition-colors"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      )}

      {/* Knowledge base */}
      <div className="card space-y-4">
        <h2 className="text-sm font-semibold text-gray-300">📚 Knowledge Base</h2>

        {/* Upload file */}
        <div>
          <label className="text-xs text-gray-500 mb-2 block">Upload PDF / Text File</label>
          <div
            className="border-2 border-dashed border-gray-700 rounded-xl p-8 text-center cursor-pointer hover:border-brand-500 transition-colors"
            onClick={() => fileRef.current?.click()}
          >
            <span className="text-3xl">📄</span>
            <p className="text-gray-400 text-sm mt-2">
              {uploading ? "Uploading..." : "Click to upload PDF, TXT or MD"}
            </p>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.txt,.md"
              className="hidden"
              onChange={handleFileUpload}
            />
          </div>
        </div>

        {/* URL ingest */}
        <div>
          <label className="text-xs text-gray-500 mb-2 block">Ingest from URL</label>
          <div className="flex gap-2">
            <input
              type="url"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-500"
              placeholder="https://your-docs.com/faq"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleUrlIngest()}
            />
            <button
              onClick={handleUrlIngest}
              disabled={uploading || !urlInput}
              className="bg-brand-600 hover:bg-brand-700 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              Add
            </button>
          </div>
        </div>

        {/* Source list */}
        {sources.length > 0 && (
          <div>
            <p className="text-xs text-gray-500 mb-2">Ingested Sources ({sources.length})</p>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {sources.map((s) => (
                <div
                  key={s.source}
                  className="flex items-center justify-between bg-gray-800 rounded-lg px-3 py-2"
                >
                  <span className="text-xs text-gray-300 truncate max-w-xs" title={s.source}>
                    📄 {s.source}
                  </span>
                  <button
                    onClick={() => handleDeleteSource(s.source)}
                    className="text-red-500 hover:text-red-400 text-xs ml-4 shrink-0"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
