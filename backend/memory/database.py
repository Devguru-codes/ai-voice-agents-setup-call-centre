"""
Database models and async session management via SQLAlchemy.
"""
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, Enum,
    ForeignKey, JSON, func
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

import config

logger = logging.getLogger(__name__)


# ── SQLAlchemy Base ───────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True)  # phone number or generated ID
    name = Column(String, nullable=True)
    company = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    lead_status = Column(
        Enum("new", "qualified", "disqualified", "customer", name="lead_status"),
        default="new"
    )
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    calls = relationship("Call", back_populates="customer", lazy="select")


class Call(Base):
    __tablename__ = "calls"

    id = Column(String, primary_key=True)  # LiveKit room name / UUID
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True)
    started_at = Column(DateTime, default=func.now())
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    sentiment = Column(
        Enum("positive", "neutral", "negative", name="call_sentiment"),
        nullable=True
    )
    lead_score = Column(Integer, nullable=True)   # 1-10
    action_items = Column(JSON, nullable=True)    # list[str]
    agent_used = Column(String, nullable=True)    # e.g. "sales"
    recording_url = Column(String, nullable=True)

    customer = relationship("Customer", back_populates="calls")


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # "pdf" | "url"
    chunk_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=func.now())


class AgentConfig(Base):
    __tablename__ = "agent_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String, default="Acme Corp")
    greeting = Column(Text, default="Hello! I'm your AI assistant. How can I help you today?")
    business_hours = Column(String, default="9am-5pm Mon-Fri")
    escalation_email = Column(String, nullable=True)
    voice_id = Column(String, default="21m00Tcm4TlvDq8ikWAM")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ── Engine & Session Factory ──────────────────────────────────────────────────

engine = create_async_engine(
    config.DATABASE_URL,
    echo=config.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async database session."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables on startup."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created/verified")

        # Seed default agent config if missing
        async with AsyncSessionFactory() as session:
            from sqlalchemy import select
            result = await session.execute(select(AgentConfig).limit(1))
            if not result.scalar_one_or_none():
                session.add(AgentConfig())
                await session.commit()
                logger.info("✅ Default agent config seeded")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
