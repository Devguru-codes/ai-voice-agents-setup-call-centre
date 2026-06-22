"""
RAG document ingestion pipeline.

Supports:
  - PDF files (via PyPDF2 / langchain PyPDFLoader)
  - Plain text / markdown
  - Website URLs (basic scrape)

All text is chunked and embedded using HuggingFace sentence-transformers
then stored in a local ChromaDB vector store.
"""
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
COLLECTION_NAME = "company_knowledge"


def _get_chroma():
    """Return the ChromaDB collection, creating it if needed."""
    import chromadb
    from chromadb.config import Settings
    import config

    client = chromadb.PersistentClient(
        path=str(config.CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def _get_embedder():
    """Return the HuggingFace sentence-transformer embedder."""
    from langchain_community.embeddings import HuggingFaceEmbeddings
    import config

    return HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


async def ingest_pdf(file_path: str, filename: str) -> int:
    """
    Ingest a PDF file into ChromaDB.

    Returns:
        Number of chunks ingested.
    """
    try:
        from langchain_community.document_loaders import PyPDFLoader
        loader = PyPDFLoader(file_path)
        pages = loader.load()
        full_text = "\n\n".join(p.page_content for p in pages)
    except Exception as e:
        logger.error(f"❌ PDF load error for {filename}: {e}")
        raise

    return await _ingest_text(full_text, source=filename)


async def ingest_url(url: str) -> int:
    """
    Scrape a webpage and ingest its text content.

    Returns:
        Number of chunks ingested.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        full_text = soup.get_text(separator="\n", strip=True)

    except Exception as e:
        logger.error(f"❌ URL scrape error for {url}: {e}")
        raise

    return await _ingest_text(full_text, source=url)


async def ingest_text_file(file_path: str, filename: str) -> int:
    """Ingest a plain text or markdown file."""
    try:
        text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"❌ Text file read error for {filename}: {e}")
        raise
    return await _ingest_text(text, source=filename)


async def _ingest_text(text: str, source: str) -> int:
    """Core ingestion: chunk → embed → store in ChromaDB."""
    if not text.strip():
        logger.warning(f"⚠️ Empty text from source: {source}")
        return 0

    try:
        chunks = _chunk_text(text)
        if not chunks:
            return 0

        embedder = _get_embedder()
        collection = _get_chroma()

        embeddings = embedder.embed_documents(chunks)
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [{"source": source, "chunk_index": i} for i in range(len(chunks))]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        logger.info(f"✅ Ingested {len(chunks)} chunks from: {source}")
        return len(chunks)

    except Exception as e:
        logger.error(f"❌ Ingestion error for {source}: {e}")
        raise


async def delete_source(source_name: str) -> int:
    """Delete all chunks from a given source."""
    try:
        collection = _get_chroma()
        results = collection.get(where={"source": source_name})
        ids = results.get("ids", [])
        if ids:
            collection.delete(ids=ids)
            logger.info(f"🗑️ Deleted {len(ids)} chunks from: {source_name}")
        return len(ids)
    except Exception as e:
        logger.error(f"❌ Delete error for {source_name}: {e}")
        return 0
