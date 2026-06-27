# AI Voice Customer Success Platform

Enterprise-grade AI voice agents designed to seamlessly handle inbound and outbound calls, completely replacing traditional call center workflows. 

Think of it as: **Retell AI + Bland AI + Vapi + HubSpot** combined into an open-source, deployable stack.

## Overview

This platform features a robust, real-time voice pipeline that streams audio to and from the browser via WebSockets. It uses state-of-the-art models for speech recognition, LLM reasoning, and voice synthesis, all orchestrated asynchronously with sub-second latency.

### Core Capabilities
- **Real-time Voice Pipeline**: Deepgram (STT) ⚡ Groq Llama-3 (LLM) ⚡ Edge TTS (TTS).
- **Multi-Agent Swarm**: Hot-swapping agent personas (Receptionist, Sales, Support) seamlessly during a live call based on conversation context.
- **Tool Calling & CRM**: Agents can dynamically execute tools (e.g., booking Calendar events, sending Emails, updating the CRM) during the conversation.
- **RAG & Knowledge Base**: Upload PDFs, text files, or ingest URLs. The system automatically chunks, embeds (via HuggingFace CPU models), and stores them in a local ChromaDB instance for semantic search during calls.
- **Call Analytics**: Post-call asynchronous processing extracts summary, sentiment, lead score, and actionable items, saving them to PostgreSQL.
- **Beautiful Dashboard**: A Next.js frontend with Tailwind CSS providing real-time KPI tracking, interactive charts, and live call testing interfaces.

## Architecture

```text
                 Incoming Call
                      │
               WebSocket / PCM Audio
                      │
┌─────────────────────▼─────────────────────┐
│             ConversationManager           │
│                                           │
│  ┌────────────┐   ┌────────────┐          │
│  │ Deepgram   │   │ Groq API   │          │
│  │ (STT)      ├──►│ Llama-3    ├────────┐ │
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

## Getting Started

### 1. Prerequisites
- Docker & Docker Compose
- API Keys for:
  - **Groq** (LLM inference)
  - **Deepgram** (Speech-to-Text)

### 2. Configuration
Copy the environment template and fill in your keys:
```bash
cp .env.example .env
# Edit .env with your favorite editor
```

### 3. Run with Docker Compose
The easiest way to spin up the entire stack (PostgreSQL, Redis, FastAPI Backend, Next.js Frontend) is via Docker Compose.
```bash
cd docker
docker-compose up --build
```

### 4. Access the Application
- **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
- **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

## Development Setup (Local without Docker)

If you prefer to run services individually for development:

**1. Infrastructure**
Start PostgreSQL and Redis locally.

**2. Backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**3. Frontend**
```bash
cd frontend
npm install
npm run dev
```

## Tech Stack
- **Frontend**: Next.js 14, React 18, Tailwind CSS, Recharts
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, Alembic, Redis (asyncio)
- **AI/ML**: Groq (Llama-3-70b-versatile), Deepgram, Edge TTS, LangChain, ChromaDB, HuggingFace Sentence Transformers
- **Infrastructure**: Docker, Docker Compose, PostgreSQL, Redis

## License
MIT License
