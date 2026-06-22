"""
RAG semantic search retriever.
Queries ChromaDB to find the most relevant knowledge-base chunks for a query.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TOP_K = 3
MIN_RELEVANCE = 0.35  # Cosine distance threshold (lower = more similar)


def _get_chroma():
    import chromadb
    from chromadb.config import Settings
    import config
    client = chromadb.PersistentClient(
        path=str(config.CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection("company_knowledge")


def _get_embedder():
    from langchain_community.embeddings import HuggingFaceEmbeddings
    import config
    return HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


async def search_docs(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Perform a semantic search over the knowledge base.

    Returns:
        List of dicts: [{text, source, score}]
    """
    if not query.strip():
        return []

    try:
        embedder = _get_embedder()
        query_embedding = embedder.embed_query(query)

        collection = _get_chroma()
        count = collection.count()
        if count == 0:
            logger.info("Knowledge base is empty — no docs ingested yet")
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

        docs = []
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )):
            # Convert cosine distance to similarity (lower distance = higher similarity)
            similarity = 1.0 - dist
            if similarity < MIN_RELEVANCE:
                continue
            docs.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "score": round(similarity, 3),
            })

        logger.debug(f"RAG search '{query}': {len(docs)} results above threshold")
        return docs

    except Exception as e:
        logger.error(f"❌ RAG retriever error: {e}")
        return []


async def list_sources() -> list[dict]:
    """List all distinct sources in the knowledge base."""
    try:
        collection = _get_chroma()
        all_meta = collection.get(include=["metadatas"])["metadatas"]
        seen: set[str] = set()
        sources = []
        for meta in all_meta:
            src = meta.get("source", "unknown")
            if src not in seen:
                seen.add(src)
                sources.append({"source": src})
        return sources
    except Exception as e:
        logger.error(f"❌ list_sources error: {e}")
        return []
