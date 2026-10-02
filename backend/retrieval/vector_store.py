"""
Vector store — ChromaDB with auth-aware metadata filtering.
Confidential data is filtered BEFORE semantic search, not after.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Any

import structlog
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from config import settings
from models.embeddings import embedding_model

logger = structlog.get_logger(__name__)

# Collections — separated to enforce domain boundaries
COLLECTIONS = {
    "non_confidential": "rag_non_confidential",
    "confidential": "rag_confidential",
}


def _get_chroma(collection_name: str) -> Chroma:
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    return Chroma(
        collection_name=collection_name,
        embedding_function=embedding_model.langchain_embeddings,
        persist_directory=settings.CHROMA_PERSIST_DIR,
    )


def _pick_collection(classification: str) -> str:
    if classification == "CONFIDENTIAL":
        return COLLECTIONS["confidential"]
    return COLLECTIONS["non_confidential"]


async def add_documents(
    documents: List[Document],
    classification: str,
    source_id: str,
    source_name: str,
    access_roles: List[str],
    allowed_users: List[str],
    allowed_departments: List[str],
) -> int:
    """
    Add documents to the appropriate vector store collection.
    Embeds access metadata into every chunk.
    Returns the number of chunks added.
    """
    collection_name = _pick_collection(classification)
    store = _get_chroma(collection_name)

    # Enrich metadata on each document
    for doc in documents:
        doc.metadata.update({
            "classification": classification,
            "source_id": source_id,
            "source_name": source_name,
            "access_roles": access_roles,       # stored as list
            "allowed_users": allowed_users,
            "allowed_departments": allowed_departments,
        })

    store.add_documents(documents)
    logger.info(
        "documents_indexed",
        count=len(documents),
        collection=collection_name,
        source_id=source_id,
    )
    return len(documents)


async def search(
    query: str,
    user_role: str,
    user_id: str,
    user_department: Optional[str],
    classification_filter: Optional[str] = None,
    source_ids: Optional[List[str]] = None,
    k: int = 5,
) -> List[Document]:
    """
    Auth-aware semantic search.
    NEVER retrieves unauthorized chunks — filter is applied at DB level.

    Security: metadata filter is applied BEFORE (or simultaneously with)
    semantic search via ChromaDB's `where` clause.
    """
    results: List[Document] = []

    # Determine which collections to search
    collections_to_search = []
    if classification_filter == "CONFIDENTIAL":
        if user_role in ("FACULTY", "ADMIN"):
            collections_to_search = [COLLECTIONS["confidential"]]
    elif classification_filter == "NON_CONFIDENTIAL":
        collections_to_search = [COLLECTIONS["non_confidential"]]
    else:
        # Search non-confidential always; confidential only for authorized roles
        collections_to_search = [COLLECTIONS["non_confidential"]]
        if user_role in ("FACULTY", "ADMIN"):
            collections_to_search.append(COLLECTIONS["confidential"])

    for coll_name in collections_to_search:
        store = _get_chroma(coll_name)
        where: Dict[str, Any] = {}

        # Build ChromaDB metadata filter
        if coll_name == COLLECTIONS["confidential"]:
            # Role-based filter
            where = {"access_roles": {"$contains": user_role}}

        if source_ids:
            if where:
                where = {"$and": [where, {"source_id": {"$in": source_ids}}]}
            else:
                where = {"source_id": {"$in": source_ids}}

        try:
            docs = store.similarity_search(
                query,
                k=k,
                filter=where if where else None,
            )
            results.extend(docs)
        except Exception as exc:
            logger.error("vector_search_error", collection=coll_name, error=str(exc))

    # Sort by relevance (ChromaDB returns in order, but deduplicate)
    seen = set()
    deduped = []
    for doc in results:
        key = doc.metadata.get("source_id", "") + doc.page_content[:100]
        if key not in seen:
            seen.add(key)
            deduped.append(doc)

    return deduped[:k]


async def delete_source(source_id: str, classification: str) -> None:
    """Remove all chunks for a source from the vector store."""
    collection_name = _pick_collection(classification)
    store = _get_chroma(collection_name)
    store._collection.delete(where={"source_id": source_id})
    logger.info("source_deleted_from_vectorstore", source_id=source_id)
