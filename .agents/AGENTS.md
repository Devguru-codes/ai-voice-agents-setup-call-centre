# Custom Rules for voice-agent

## General Rules
- Always commit changes to the local git repository (push to local git) after completing a significant chunk of work.
- Maintain the architectural boundaries and follow the stack conventions outlined below.

## Project Context: AI Voice Customer Success Platform
This project is an Enterprise-grade AI voice agent platform designed to seamlessly handle inbound and outbound calls, completely replacing traditional call center workflows. It combines features comparable to Retell AI, Bland AI, Vapi, and HubSpot into a single open-source, deployable stack.

### Core Capabilities
- **Real-time Voice Pipeline:** Streams audio to/from the browser via WebSockets with sub-second latency. Powered by Faster Whisper (STT) ⚡ Groq Llama-3 (LLM) ⚡ Edge TTS (TTS).
- **Multi-Agent Swarm:** Hot-swapping agent personas (Receptionist, Sales, Support) seamlessly during a live call based on conversation context via the `ConversationManager`.
- **Tool Calling & CRM:** Agents dynamically execute tools during conversations, such as booking Calendar events, sending Emails, and updating the CRM.
- **RAG & Knowledge Base:** Supports PDF, text, and URL ingestion. Automatically chunks, embeds (via HuggingFace CPU models), and stores them in a local ChromaDB instance for semantic search during calls.
- **Call Analytics:** Asynchronous post-call processing extracts summaries, sentiment, lead scores, and actionable items, saving them to PostgreSQL.
- **Beautiful Dashboard:** A Next.js frontend with Tailwind CSS providing real-time KPI tracking, interactive charts, and live call testing interfaces.

### Tech Stack
- **Frontend**: Next.js 14, React 18, Tailwind CSS, Recharts
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, Alembic, Redis (asyncio)
- **AI/ML**: Groq (Llama-3-70b-versatile), Faster Whisper, Edge TTS, LangChain, ChromaDB, HuggingFace Sentence Transformers
- **Infrastructure**: Docker, Docker Compose, PostgreSQL, Redis

### Architecture Flow
```text
                 Incoming Call
                      │
               WebSocket / PCM Audio
                      │
┌─────────────────────▼─────────────────────┐
│             ConversationManager           │
│                                           │
│  ┌──────────────┐ ┌────────────┐          │
│  │ Faster Whisper │ │ Groq API   │          │
│  │ (STT)          ├─► Llama-3    ├────────┐ │
│  └────────────┘   └──────┬─────┘        │ │
│                          │              │ │
│                   ┌──────▼─────┐  ┌─────▼─▼────┐
│                   │ Tools / RAG│  │ Edge TTS   │
│                   └────────────┘  │ (TTS)      │
│                                   └─────┬──────┘
└─────────────────────────────────────────┼─┘
                                          │
                                 WebSocket / Audio Out
                                          ▼
                                      Customer
```

### Automated Testing (CI/CD)
- **Backend Tests:** Located in `backend/tests/` (run with `pytest`). Covers agent registry, tools, and mock checks for AI services.
- **Frontend Tests:** Located in `frontend/test/` (run with `npm test` using Jest & React Testing Library).
- **CI/CD:** Configured via GitHub Actions in `.github/workflows/test.yml` to automatically run tests on PRs and pushes to `main`.
