"""
FastAPI routes — REST + WebSocket endpoints.

Endpoints:
  POST   /api/calls/token          — Issue LiveKit JWT for a caller
  GET    /api/analytics/summary    — Dashboard KPIs
  GET    /api/calls                — Paginated call list
  GET    /api/calls/{id}           — Single call detail
  POST   /api/knowledge/upload     — PDF/text upload → RAG ingestion
  POST   /api/knowledge/url        — URL → RAG ingestion
  GET    /api/knowledge/sources    — List ingested sources
  DELETE /api/knowledge/sources/{name} — Remove a source
  GET    /api/settings             — Get agent config
  PUT    /api/settings             — Update agent config
  WS     /ws/call/{call_id}        — Real-time voice call WebSocket
"""
import asyncio
import base64
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException,
    UploadFile, WebSocket, WebSocketDisconnect, BackgroundTasks
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

import config
from memory.database import (
    get_db, Call, Customer, KnowledgeDoc, AgentConfig, AsyncSessionFactory
)
from memory.session import session_manager
from agents.conversation_manager import ConversationManager
from services.stt_service import STTService
from services.tts_service import TTSService
from api.tasks import process_call_end
from rag.ingest import ingest_pdf, ingest_url, ingest_text_file, delete_source
from rag.retriever import list_sources

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    customer_id: Optional[str] = None


class TokenResponse(BaseModel):
    token: str
    room_name: str
    livekit_url: str


class SettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    greeting: Optional[str] = None
    business_hours: Optional[str] = None
    escalation_email: Optional[str] = None
    voice_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Call token
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/calls/token", response_model=TokenResponse)
async def get_call_token(req: TokenRequest):
    """Issue a LiveKit JWT for a new call session."""
    try:
        from livekit.api import AccessToken, VideoGrants
        room_name = f"call-{uuid.uuid4().hex[:8]}"
        token = (
            AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
            .with_identity(req.customer_id or "caller")
            .with_name("Caller")
            .with_grants(VideoGrants(room_join=True, room=room_name))
            .to_jwt()
        )
        return TokenResponse(
            token=token,
            room_name=room_name,
            livekit_url=config.LIVEKIT_URL,
        )
    except Exception as e:
        logger.error(f"❌ Token generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Token generation failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket: real-time voice call
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/call/{call_id}")
async def voice_call_ws(websocket: WebSocket, call_id: str):
    """
    WebSocket endpoint for a live voice call.

    Protocol:
      Client → Server: binary PCM audio frames (16kHz, mono, 16-bit)
      Server → Client: JSON messages
        {type: "text", text: "..."}       — LLM token (for display)
        {type: "audio", data: "<base64>"}  — TTS PCM audio chunk
        {type: "agent", name: "sales"}     — Agent switched
        {type: "error", message: "..."}
    """
    await websocket.accept()
    logger.info(f"🔌 WebSocket connected: {call_id}")

    call_start = datetime.utcnow()
    customer_id = websocket.query_params.get("customer_id")
    current_agent = "receptionist"

    async def send_json(data: dict):
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    async def on_tts_audio(pcm: bytes):
        """Forward TTS audio to the browser."""
        await send_json({"type": "audio", "data": base64.b64encode(pcm).decode()})

    async def on_text_chunk(text: str):
        """Forward LLM text token to the browser for display."""
        await send_json({"type": "text", "text": text})
        if tts:
            await tts.send_text(text)

    async def on_agent_changed(agent_name: str):
        from agents.registry import get_agent_voice
        nonlocal current_agent
        current_agent = agent_name
        if tts:
            voice_id = get_agent_voice(agent_name)
            if voice_id:
                tts.set_voice(voice_id)
        await send_json({"type": "agent", "name": agent_name})

    async def on_tts_flush():
        """Flush TTS buffer — called by ConversationManager after transfers."""
        if tts:
            await tts.flush()

    # Initialize services
    stt: Optional[STTService] = None
    tts: Optional[TTSService] = None
    manager: Optional[ConversationManager] = None

    async def on_final_transcript(text: str):
        """Called by STT when a full sentence is transcribed."""
        logger.debug(f"📝 Final transcript: {text}")
        await send_json({"type": "user", "text": text})
        if manager:
            await manager.handle_transcript(text)
        # After manager sends text tokens, flush TTS
        if tts:
            await tts.flush()

    try:
        # Initialize STT
        stt = STTService(on_final=on_final_transcript)
        await stt.start()

        # Initialize TTS
        tts = TTSService(on_audio=on_tts_audio)
        await tts.start()

        # Initialize conversation manager
        manager = ConversationManager(
            call_id=call_id,
            on_text_chunk=on_text_chunk,
            on_agent_changed=on_agent_changed,
            on_tts_flush=on_tts_flush,
        )
        await manager.start(customer_id=customer_id)
        if tts:
            await tts.flush()

        # Main loop: receive audio from browser, pipe to Faster Whisper
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send a keepalive ping
                await send_json({"type": "ping"})
                continue

            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes"):
                await stt.send_audio(msg["bytes"])
            elif msg.get("text"):
                # Control messages from frontend (e.g., {"type":"end"})
                try:
                    ctrl = json.loads(msg["text"])
                    if ctrl.get("type") == "end":
                        break
                except Exception:
                    pass

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected: {call_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket error on {call_id}: {e}")
        await send_json({"type": "error", "message": str(e)})
    finally:
        # Cleanup safely
        import contextlib
        transcript = ""
        
        with contextlib.suppress(Exception):
            if manager:
                transcript = await manager.stop()
                
        with contextlib.suppress(Exception):
            if tts:
                await tts.stop()
                
        with contextlib.suppress(Exception):
            if stt:
                await stt.stop()

        # Calculate duration
        duration = (datetime.utcnow() - call_start).total_seconds()

        # Run post-call analytics in the background
        asyncio.create_task(
            process_call_end(
                call_id=call_id,
                customer_id=customer_id,
                agent_used=current_agent,
                duration_seconds=duration,
            )
        )
        logger.info(f"✅ Call {call_id} ended ({duration:.0f}s)")


# ─────────────────────────────────────────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/analytics/summary")
async def analytics_summary(db: AsyncSession = Depends(get_db)):
    """Dashboard KPIs: total calls, avg duration, sentiment breakdown, avg lead score."""
    try:
        total = (await db.execute(select(func.count(Call.id)))).scalar() or 0
        avg_dur = (await db.execute(select(func.avg(Call.duration_seconds)))).scalar() or 0.0
        avg_score = (await db.execute(select(func.avg(Call.lead_score)))).scalar() or 0.0

        sentiment_rows = await db.execute(
            select(Call.sentiment, func.count(Call.id))
            .group_by(Call.sentiment)
        )
        sentiment = {row[0] or "unknown": row[1] for row in sentiment_rows}

        # Recent 7-day trend
        from sqlalchemy import cast, Date, text
        trend_rows = await db.execute(
            select(
                func.date_trunc("day", Call.started_at).label("day"),
                func.count(Call.id).label("count")
            )
            .where(Call.started_at >= text("NOW() - INTERVAL '7 days'"))
            .group_by(text("day"))
            .order_by(text("day"))
        )
        trend = [{"date": str(r.day)[:10], "calls": r.count} for r in trend_rows]

        return {
            "total_calls": total,
            "avg_duration_seconds": round(float(avg_dur), 1),
            "avg_lead_score": round(float(avg_score), 1),
            "sentiment": sentiment,
            "trend": trend,
        }
    except Exception as e:
        logger.error(f"❌ Analytics summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Call list & detail
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/calls")
async def list_calls(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Paginated call list, newest first."""
    try:
        offset = (page - 1) * page_size
        total = (await db.execute(select(func.count(Call.id)))).scalar() or 0
        rows = (await db.execute(
            select(Call).order_by(desc(Call.started_at)).offset(offset).limit(page_size)
        )).scalars().all()

        calls = [
            {
                "id": c.id,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "duration_seconds": c.duration_seconds,
                "sentiment": c.sentiment,
                "lead_score": c.lead_score,
                "agent_used": c.agent_used,
                "summary": c.summary,
                "customer_id": c.customer_id,
            }
            for c in rows
        ]
        return {"total": total, "page": page, "page_size": page_size, "calls": calls}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/calls/{call_id}")
async def get_call(call_id: str, db: AsyncSession = Depends(get_db)):
    """Full call detail including transcript and action items."""
    result = await db.execute(select(Call).where(Call.id == call_id))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return {
        "id": call.id,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "duration_seconds": call.duration_seconds,
        "transcript": call.transcript,
        "summary": call.summary,
        "sentiment": call.sentiment,
        "lead_score": call.lead_score,
        "action_items": call.action_items or [],
        "agent_used": call.agent_used,
        "customer_id": call.customer_id,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge base
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/knowledge/upload")
async def upload_knowledge(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF or text file to the knowledge base."""
    filename = file.filename or f"upload_{uuid.uuid4().hex[:8]}"
    allowed_types = {
        "application/pdf",
        "text/plain",
        "text/markdown",
    }
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, TXT, MD"
        )

    # Save to temp file
    suffix = ".pdf" if "pdf" in (file.content_type or "") else ".txt"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")

    async def run_ingest():
        try:
            if suffix == ".pdf":
                chunk_count = await ingest_pdf(tmp_path, filename)
            else:
                chunk_count = await ingest_text_file(tmp_path, filename)

            async with AsyncSessionFactory() as session:
                doc = KnowledgeDoc(
                    filename=filename,
                    source_type="pdf" if suffix == ".pdf" else "text",
                    chunk_count=chunk_count,
                )
                session.add(doc)
                await session.commit()
        except Exception as e:
            logger.error(f"❌ Background ingest error for {filename}: {e}")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    background_tasks.add_task(run_ingest)
    return {"message": f"'{filename}' queued for ingestion.", "filename": filename}


@router.post("/api/knowledge/url")
async def ingest_knowledge_url(
    url: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """Scrape a URL and add it to the knowledge base."""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    async def run_ingest():
        try:
            chunk_count = await ingest_url(url)
            async with AsyncSessionFactory() as session:
                doc = KnowledgeDoc(
                    filename=url, source_type="url", chunk_count=chunk_count
                )
                session.add(doc)
                await session.commit()
        except Exception as e:
            logger.error(f"❌ URL ingest error for {url}: {e}")

    background_tasks.add_task(run_ingest)
    return {"message": f"URL '{url}' queued for ingestion."}


@router.get("/api/knowledge/sources")
async def get_sources():
    """List all ingested knowledge base sources."""
    try:
        sources = await list_sources()
        return {"sources": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/knowledge/sources/{source_name:path}")
async def remove_source(source_name: str):
    """Delete all chunks from a knowledge base source."""
    try:
        count = await delete_source(source_name)
        return {"deleted_chunks": count, "source": source_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Settings (agent config)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentConfig).limit(1))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="No config found")
    return {
        "company_name": cfg.company_name,
        "greeting": cfg.greeting,
        "business_hours": cfg.business_hours,
        "escalation_email": cfg.escalation_email,
        "voice_id": cfg.voice_id,
    }


@router.put("/api/settings")
async def update_settings(
    update: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentConfig).limit(1))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="No config found")

    if update.company_name is not None:
        cfg.company_name = update.company_name
    if update.greeting is not None:
        cfg.greeting = update.greeting
    if update.business_hours is not None:
        cfg.business_hours = update.business_hours
    if update.escalation_email is not None:
        cfg.escalation_email = update.escalation_email
    if update.voice_id is not None:
        cfg.voice_id = update.voice_id

    await db.commit()
    return {"message": "Settings updated."}


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
