"""
Post-call analytics processing.

When a call ends, this background task sends the transcript to Groq
to extract: summary, sentiment, lead_score, action_items.
Results are persisted to PostgreSQL.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from memory.database import Call, Customer, AsyncSessionFactory
from services.llm_service import llm_service
from memory.session import session_manager

logger = logging.getLogger(__name__)

ANALYTICS_PROMPT = """You are a call analysis expert. Analyze this call transcript and return a JSON object with exactly these fields:
- summary: string (2-3 sentences summarizing the call)
- sentiment: string (exactly one of: "positive", "neutral", "negative")
- lead_score: integer (1-10, where 10 is most qualified/interested)
- action_items: array of strings (concrete next steps, empty array if none)

Return ONLY valid JSON, no markdown, no explanation.

Transcript:
{transcript}"""


async def process_call_end(
    call_id: str,
    customer_id: Optional[str] = None,
    agent_used: Optional[str] = None,
    duration_seconds: Optional[float] = None,
) -> dict:
    """
    Run post-call analytics pipeline:
    1. Fetch full transcript from Redis
    2. Send to Groq for structured analysis
    3. Save everything to PostgreSQL
    4. Clean up Redis session

    Returns the analytics dict.
    """
    logger.info(f"📊 Starting post-call analytics: {call_id}")

    # Fetch transcript
    transcript = await session_manager.get_transcript(call_id)
    if not transcript.strip():
        logger.warning(f"⚠️ No transcript found for call {call_id}")
        transcript = "(No transcript available)"

    # Extract analytics via Groq
    analytics = await _extract_analytics(transcript)

    # Persist to DB
    await _save_call(
        call_id=call_id,
        customer_id=customer_id,
        transcript=transcript,
        analytics=analytics,
        agent_used=agent_used,
        duration_seconds=duration_seconds,
    )

    # Clean up Redis session
    await session_manager.delete_session(call_id)

    logger.info(
        f"✅ Analytics complete for {call_id}: "
        f"sentiment={analytics.get('sentiment')}, "
        f"lead_score={analytics.get('lead_score')}"
    )
    return analytics


async def _extract_analytics(transcript: str) -> dict:
    """Call Groq to extract structured analytics from transcript."""
    default = {
        "summary": "Call transcript analysis unavailable.",
        "sentiment": "neutral",
        "lead_score": 5,
        "action_items": [],
    }

    try:
        prompt = ANALYTICS_PROMPT.format(transcript=transcript[:6000])  # Limit tokens
        response = await llm_service.complete(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        data = json.loads(response)

        # Validate and coerce types
        sentiment = str(data.get("sentiment", "neutral")).lower()
        if sentiment not in {"positive", "neutral", "negative"}:
            sentiment = "neutral"

        lead_score = int(data.get("lead_score", 5))
        lead_score = max(1, min(10, lead_score))

        action_items = data.get("action_items", [])
        if not isinstance(action_items, list):
            action_items = []

        return {
            "summary": str(data.get("summary", "")),
            "sentiment": sentiment,
            "lead_score": lead_score,
            "action_items": action_items,
        }

    except json.JSONDecodeError as e:
        logger.error(f"❌ Analytics JSON parse error: {e}")
        return default
    except Exception as e:
        logger.error(f"❌ Analytics extraction failed: {e}")
        return default


async def _save_call(
    call_id: str,
    customer_id: Optional[str],
    transcript: str,
    analytics: dict,
    agent_used: Optional[str],
    duration_seconds: Optional[float],
) -> None:
    """Persist the call and analytics to PostgreSQL."""
    try:
        async with AsyncSessionFactory() as session:
            call = Call(
                id=call_id,
                customer_id=customer_id,
                ended_at=datetime.utcnow(),
                duration_seconds=duration_seconds,
                transcript=transcript,
                summary=analytics.get("summary"),
                sentiment=analytics.get("sentiment"),
                lead_score=analytics.get("lead_score"),
                action_items=analytics.get("action_items", []),
                agent_used=agent_used,
            )
            session.add(call)
            await session.commit()
            logger.info(f"💾 Call saved to DB: {call_id}")
    except Exception as e:
        logger.error(f"❌ Failed to save call {call_id}: {e}")
