"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { getCallToken } from "@/lib/api";

type WsMessage =
  | { type: "text"; text: string }
  | { type: "audio"; data: string }
  | { type: "agent"; name: string }
  | { type: "interim"; text: string }
  | { type: "error"; message: string }
  | { type: "ping" };

type CallStatus = "idle" | "connecting" | "connected" | "ended" | "error";

const AGENT_LABELS: Record<string, string> = {
  receptionist: "🏢 Receptionist",
  sales: "💼 Sales Agent",
  support: "🛠️ Support Agent",
  scheduling: "📅 Scheduling Agent",
};

export default function LiveCallPage() {
  const [status, setStatus] = useState<CallStatus>("idle");
  const [agent, setAgent] = useState("receptionist");
  const agentRef = useRef("receptionist");
  const [transcript, setTranscript] = useState<{ role: string; text: string; agent: string }[]>([]);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [callId, setCallId] = useState<string | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [micVolume, setMicVolume] = useState<number>(0);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const nextPlayTimeRef = useRef<number>(0);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const appendTranscript = useCallback((role: string, text: string) => {
    setTranscript((prev) => [...prev, { role, text, agent: agentRef.current }]);
    setTimeout(() => transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }, []);

  const playAudio = useCallback(async (base64: string) => {
    try {
      const ctx = audioCtxRef.current || new AudioContext({ sampleRate: 16000 });
      audioCtxRef.current = ctx;

      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

      // PCM 16-bit → Float32
      const pcm = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(pcm.length);
      for (let i = 0; i < pcm.length; i++) float32[i] = pcm[i] / 32768.0;

      const buffer = ctx.createBuffer(1, float32.length, 16000);
      buffer.getChannelData(0).set(float32);

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      
      if (nextPlayTimeRef.current < ctx.currentTime) {
        nextPlayTimeRef.current = ctx.currentTime;
      }
      
      source.start(nextPlayTimeRef.current);
      nextPlayTimeRef.current += buffer.duration;
    } catch (e) {
      console.error("Audio playback error:", e);
    }
  }, []);

  const startCall = async () => {
    setError(null);
    setStatus("connecting");
    setTranscript([]);
    setAgent("receptionist");

    try {
      // Get a LiveKit-style token / room name from backend
      const tokenData = await getCallToken();
      const roomName = tokenData.room_name;
      setCallId(roomName);

      // Open WebSocket
      const wsUrl = `${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace("http", "ws")}/ws/call/${roomName}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = async () => {
        setStatus("connected");

        // Get microphone
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        mediaRef.current = stream;

        const ctx = new AudioContext({ sampleRate: 16000 });
        audioCtxRef.current = ctx;
        const source = ctx.createMediaStreamSource(stream);
        const processor = ctx.createScriptProcessor(4096, 1, 1);
        processorRef.current = processor;

        processor.onaudioprocess = (e) => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const float32 = e.inputBuffer.getChannelData(0);
          
          let sumSquares = 0;
          for (let i = 0; i < float32.length; i++) {
            sumSquares += float32[i] * float32[i];
          }
          const rms = Math.sqrt(sumSquares / float32.length);
          setMicVolume(Math.min(100, Math.floor(rms * 100 * 5)));
          
          // Convert Float32 → Int16 PCM
          const pcm = new Int16Array(float32.length);
          for (let i = 0; i < float32.length; i++) {
            pcm[i] = Math.max(-32768, Math.min(32767, float32[i] * 32768));
          }
          ws.send(pcm.buffer);
        };

        source.connect(processor);
        processor.connect(ctx.destination);
      };

      ws.onmessage = (event) => {
        try {
          const msg: WsMessage = JSON.parse(event.data);
          if (msg.type === "text") {
            // Accumulate agent tokens into last entry
            setTranscript((prev) => {
              const last = prev[prev.length - 1];
              if (last?.role === "agent") {
                return [...prev.slice(0, -1), { ...last, text: last.text + msg.text }];
              }
              return [...prev, { role: "agent", text: msg.text, agent: agentRef.current }];
            });
          } else if (msg.type === "audio") {
            playAudio(msg.data);
          } else if (msg.type === "agent") {
            setAgent(msg.name);
            agentRef.current = msg.name;
          } else if (msg.type === "interim") {
            setInterim(msg.text);
          } else if (msg.type === "user") {
            setInterim("");
            appendTranscript("user", msg.text);
          } else if (msg.type === "error") {
            setError(msg.message);
          }
        } catch {}
      };

      ws.onclose = () => {
        setStatus("ended");
        cleanup();
      };

      ws.onerror = () => {
        setError("WebSocket connection failed");
        setStatus("error");
        cleanup();
      };
    } catch (e: any) {
      setError(e.message || "Failed to start call");
      setStatus("error");
    }
  };

  const endCall = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "end" }));
    }
    cleanup();
    setStatus("ended");
  };

  const cleanup = () => {
    processorRef.current?.disconnect();
    mediaRef.current?.getTracks().forEach((t) => t.stop());
    wsRef.current?.close();
    audioCtxRef.current?.close();
    processorRef.current = null;
    mediaRef.current = null;
    nextPlayTimeRef.current = 0;
    setMicVolume(0);
  };

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (status === "connected") {
      interval = setInterval(() => {
        setElapsedTime((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [status]);

  useEffect(() => () => cleanup(), []);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, "0");
    const s = (seconds % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">Live Call</h1>
        <p className="text-gray-500 text-sm mt-0.5">Talk directly to the AI voice agent</p>
      </div>

      {/* Status card */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {status === "connected" && (
              <span className="w-3 h-3 bg-red-500 rounded-full pulse-ring" />
            )}
            {status === "idle" && <span className="w-3 h-3 bg-gray-600 rounded-full" />}
            {status === "connecting" && (
              <span className="w-3 h-3 bg-yellow-500 rounded-full animate-pulse" />
            )}
            {status === "ended" && <span className="w-3 h-3 bg-gray-500 rounded-full" />}
            {status === "error" && <span className="w-3 h-3 bg-red-700 rounded-full" />}
            <span className="text-gray-300 text-sm font-medium capitalize">
              {status === "connected" ? `🔴 Live - ${formatTime(elapsedTime)}` : status}
            </span>
          </div>
          <span className="text-xs text-gray-500">
            {AGENT_LABELS[agent] || agent}
          </span>
        </div>

        {callId && (
          <p className="text-xs text-gray-600 mt-2 font-mono">Call: {callId}</p>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="card border-red-800 bg-red-900/10">
          <p className="text-red-400 text-sm">⚠️ {error}</p>
        </div>
      )}

      {/* Transcript */}
      {(transcript.length > 0 || interim) && (
        <div className="card max-h-96 overflow-y-auto space-y-3">
          <h2 className="text-xs text-gray-500 uppercase font-semibold">Transcript</h2>
          {transcript.map((entry, i) => (
            <div
              key={i}
              className={`flex flex-col ${entry.role === "agent" ? "items-start" : "items-end"}`}
            >
              <span className="text-[10px] text-gray-500 mb-1 px-1">
                {entry.role === "agent" ? (AGENT_LABELS[entry.agent] || entry.agent) : "You"}
              </span>
              <div
                className={`max-w-xs px-4 py-2 rounded-2xl text-sm leading-relaxed ${
                  entry.role === "agent"
                    ? "bg-gray-800 text-gray-200 rounded-tl-sm"
                    : "bg-brand-700 text-white rounded-tr-sm"
                }`}
              >
                {entry.text}
              </div>
            </div>
          ))}
          {interim && (
            <div className="flex flex-col items-end">
              <span className="text-[10px] text-gray-500 mb-1 px-1">You</span>
              <div className="max-w-xs px-4 py-2 rounded-2xl text-sm bg-brand-900/50 text-brand-300 italic rounded-tr-sm">
                {interim}
              </div>
            </div>
          )}
          <div ref={transcriptEndRef} />
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-4">
        {(status === "idle" || status === "ended" || status === "error") && (
          <button
            onClick={startCall}
            className="flex-1 bg-brand-600 hover:bg-brand-700 text-white py-3 rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
          >
            🎙️ Start Call
          </button>
        )}
        {status === "connecting" && (
          <button disabled className="flex-1 bg-gray-700 text-gray-500 py-3 rounded-xl font-semibold cursor-not-allowed">
            Connecting...
          </button>
        )}
        {status === "connected" && (
          <div className="flex-1 flex gap-4">
            <button
              onClick={endCall}
              className="flex-1 bg-red-600 hover:bg-red-700 text-white py-3 rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
            >
              ⏹️ End Call
            </button>
            <div className="flex-1 flex items-center gap-3 bg-gray-800/50 px-4 rounded-xl border border-gray-700/50">
              <span className="text-sm text-gray-400 font-medium whitespace-nowrap">Mic:</span>
              <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-green-500 transition-all duration-75"
                  style={{ width: `${micVolume}%` }}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {status === "ended" && (
        <div className="card border-green-800 bg-green-900/10 text-center">
          <p className="text-green-400 font-medium">✅ Call ended</p>
          <p className="text-gray-500 text-xs mt-1">Analytics are being processed. View in <a href="/calls" className="text-brand-400 hover:underline">Calls →</a></p>
        </div>
      )}
    </div>
  );
}
