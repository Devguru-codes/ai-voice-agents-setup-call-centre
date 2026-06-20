"""
Backend configuration — loads from environment variables with sensible defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Base paths ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CHROMA_DIR = BASE_DIR / "rag" / "chroma_db"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# ── LLM Configuration ──────────────────────────────────────────────────────────
# Groq (Primary)
_groq_raw = os.getenv("GROQ_API_KEYS", "") or os.getenv("GROQ_API_KEY", "")
GROQ_API_KEYS: list[str] = [k.strip() for k in _groq_raw.split(",") if k.strip()]
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Ollama (Fallback)
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1")

# ── Faster Whisper (Local STT) ───────────────────────────────────────────────
# e.g., tiny.en, base.en, small.en, distil-whisper-small.en
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base.en")
WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "auto") # auto, cpu, cuda

# ── Edge TTS (Free TTS API) ──────────────────────────────────────────────────
# Default voice to use. See `edge-tts --list-voices` for more options.
EDGE_TTS_VOICE: str = os.getenv("EDGE_TTS_VOICE", "en-US-JennyNeural")

# ── LiveKit ───────────────────────────────────────────────────────────────────
LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_API_KEY: str = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "secret")

# ── Database (PostgreSQL) ─────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/voiceagent"
)

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── HuggingFace (for embeddings) ──────────────────────────────────────────────
HF_TOKEN: str = os.getenv("HF_TOKEN", "")
EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)

# ── Google OAuth (Calendar / Gmail) ──────────────────────────────────────────
GOOGLE_CLIENT_SECRETS_FILE: str = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "")

# ── App ───────────────────────────────────────────────────────────────────────
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
CORS_ORIGINS: list[str] = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000"
).split(",")
