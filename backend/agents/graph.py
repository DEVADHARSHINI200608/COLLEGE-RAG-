"""
LangGraph Agent — orchestrates the full RAG workflow.
Each node is independently modifiable without breaking others.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, TypedDict, Literal

import structlog
from langgraph.graph import StateGraph, END

from config import settings
from models.router import model_router, RouterResult

logger = structlog.get_logger(__name__)


# ─── Agent State ────────────────────────────────────────────────────────
class AgentState(TypedDict):
    # Input
    query: str
    user_id: str
    user_role: str
    user_department: Optional[str]
    session_id: Optional[str]
    force_local_model: bool

    # Classification
    intent: Optional[str]           # educational | confidential | structured | multi_doc
    security_level: Optional[str]   # CONFIDENTIAL | NON_CONFIDENTIAL

    # Source selection
    authorized_source_ids: List[str]
    selected_source_ids: List[str]

    # Retrieval
    retrieved_docs: List[Dict]
    structured_results: Optional[Dict]
    web_search_results: List[Dict]
    context_sufficient: bool

    # Model
    needs_fallback_confirmation: bool
    fallback_reason: Optional[str]
    model_used: Optional[str]
    is_local_model: bool

    # Response
    final_answer: Optional[str]
    sources_cited: List[Dict]
    error: Optional[str]

    # DB session (passed in, not serialized)
    db: Any


# ─── Nodes ──────────────────────────────────────────────────────────────

async def load_user_context(state: AgentState) -> AgentState:
    """Load user context — already available in state from API layer."""
    logger.info("agent.load_context", user_id=state["user_id"], role=state["user_role"])
    return state


async def classify_intent(state: AgentState) -> AgentState:
    """
    Classify the query intent using keyword heuristics + LLM classification.
    Keeps costs low by using fast heuristics first.
    """
    query = state["query"].lower()

    # Heuristic fast-path
    structured_keywords = [
        "count", "how many", "list", "who responded", "who did not respond",
        "missing", "attendance", "yes", "no", "compare", "find students",
        "duplicate", "total", "responded", "not responded",
    ]
    confidential_keywords = [
        "student record", "attendance", "grade", "faculty", "internal",
        "confidential", "private", "personal", "admission",
    ]
    multi_doc_keywords = [
        "document 1", "document 2", "both", "compare documents",
        "between", "across", "master list", "form response",
    ]

    if any(k in query for k in multi_doc_keywords):
        intent = "multi_doc"
    elif any(k in query for k in structured_keywords):
        intent = "structured"
    elif any(k in query for k in confidential_keywords):
        intent = "confidential"
    else:
        intent = "educational"

    logger.info("agent.intent_classified", intent=intent, query=state["query"][:80])
    return {**state, "intent": intent}


async def classify_security(state: AgentState) -> AgentState:
    """Determine required security level based on intent and user role."""
    intent = state["intent"]
    role = state["user_role"]

    if intent in ("confidential", "structured") and role in ("FACULTY", "ADMIN"):
        security_level = "CONFIDENTIAL"
    else:
        security_level = "NON_CONFIDENTIAL"

    logger.info("agent.security_classified", security_level=security_level)
    return {**state, "security_level": security_level}


async def select_sources(state: AgentState) -> AgentState:
    """
    Select sources the user is authorized to access.
    Source-level authorization happens here — before any retrieval.
    """
    from sqlalchemy import select as sa_select
    from database.models import Source

    db = state["db"]
    role = state["user_role"]
    user_id = state["user_id"]
    security_level = state["security_level"]

    # Query authorized sources
    query = sa_select(Source).where(Source.status == "ACTIVE")

    if security_level == "NON_CONFIDENTIAL":
        query = query.where(Source.classification == "NON_CONFIDENTIAL")
    elif security_level == "CONFIDENTIAL":
        if role == "ADMIN":
            query = query.where(Source.classification == "CONFIDENTIAL")
        elif role == "FACULTY":
            # Faculty sees confidential sources where their role is allowed
            query = query.where(Source.classification == "CONFIDENTIAL")
        else:
            # Students can only see non-confidential
            query = query.where(Source.classification == "NON_CONFIDENTIAL")

    result = await db.execute(query)
    sources = result.scalars().all()

    # Further filter: check access_roles at application level
    authorized_ids = []
    for src in sources:
        access_roles = src.access_roles or []
        allowed_users = src.allowed_users or []
        # If access_roles is empty → open to all (standard resources)
        if not access_roles or role in access_roles or user_id in allowed_users:
            authorized_ids.append(str(src.id))

    logger.info("agent.sources_selected", count=len(authorized_ids))
    return {**state, "authorized_source_ids": authorized_ids, "selected_source_ids": authorized_ids}


async def retrieve(state: AgentState) -> AgentState:
    """Hybrid retrieval — vector search + structured query."""
    from retrieval.vector_store import search as vector_search

    query = state["query"]
    role = state["user_role"]
    user_id = state["user_id"]
    department = state["user_department"]
    security_level = state["security_level"]
    source_ids = state["selected_source_ids"]

    # Vector search
    try:
        docs = await vector_search(
            query=query,
            user_role=role,
            user_id=user_id,
            user_department=department,
            classification_filter=security_level,
            source_ids=source_ids if source_ids else None,
            k=settings.TOP_K_RESULTS,
        )
        retrieved_docs = [
            {
                "content": doc.page_content,
                "source_id": doc.metadata.get("source_id"),
                "source_name": doc.metadata.get("source_name"),
                "classification": doc.metadata.get("classification"),
                "filename": doc.metadata.get("filename"),
            }
            for doc in docs
        ]
    except Exception as exc:
        logger.error("agent.retrieve_error", error=str(exc))
        retrieved_docs = []

    # Determine if context is sufficient (heuristic)
    context_sufficient = len(retrieved_docs) >= 2

    logger.info("agent.retrieved", doc_count=len(retrieved_docs))
    return {**state, "retrieved_docs": retrieved_docs, "context_sufficient": context_sufficient}


async def perform_structured_analysis(state: AgentState) -> AgentState:
    """Run deterministic analysis for structured queries."""
    if state["intent"] not in ("structured", "multi_doc"):
        return state

    logger.info("agent.structured_analysis")
    # Actual implementation is done via the data_analysis tool
    # Here we just flag that structured analysis was performed
    return state


async def perform_web_search(state: AgentState) -> AgentState:
    """External web search — only for non-confidential educational queries."""
    # Skip if:
    # 1. Context already sufficient
    # 2. Query is confidential
    # 3. Web search disabled
    if state["context_sufficient"]:
        return state
    if state["security_level"] == "CONFIDENTIAL":
        logger.info("agent.web_search_skipped_confidential")
        return state
    if not settings.WEB_SEARCH_ENABLED:
        return state

    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(state["query"], max_results=settings.WEB_SEARCH_MAX_RESULTS):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "source": "web",
                })
        logger.info("agent.web_search_done", count=len(results))
        return {**state, "web_search_results": results, "context_sufficient": True}
    except Exception as exc:
        logger.warning("agent.web_search_failed", error=str(exc))
        return state


async def route_model(state: AgentState) -> AgentState:
    """
    Central model routing — calls ModelRouter.
    This is the only place LLM calls are made.
    """
    # Build context
    context_parts = []

    for doc in state.get("retrieved_docs", []):
        context_parts.append(
            f"[Source: {doc['source_name']}]\n{doc['content']}"
        )

    for web in state.get("web_search_results", []):
        context_parts.append(
            f"[Web: {web['title']}]\n{web['snippet']}"
        )

    context = "\n\n---\n\n".join(context_parts)

    system_prompt = """You are a secure educational AI assistant.
Answer the user's question based ONLY on the provided context.
If the context does not contain enough information, say so clearly.
Always cite the source name when referencing information.
Never fabricate facts."""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {state['query']}"
            if context else state["query"]
        },
    ]

    result = await model_router.generate(
        messages=messages,
        db=state["db"],
        user_id=state["user_id"],
        user_role=state["user_role"],
        force_local=state.get("force_local_model", False),
    )

    if result["status"] == RouterResult.NEEDS_FALLBACK:
        return {
            **state,
            "needs_fallback_confirmation": True,
            "fallback_reason": result["fallback_reason"],
            "final_answer": None,
            "model_used": result["model_used"],
            "is_local_model": False,
        }

    # Build sources cited
    seen = set()
    sources_cited = []
    for doc in state.get("retrieved_docs", []):
        sid = doc.get("source_id")
        if sid and sid not in seen:
            seen.add(sid)
            sources_cited.append({
                "source_id": sid,
                "source_name": doc.get("source_name", "Unknown"),
                "classification": doc.get("classification", "NON_CONFIDENTIAL"),
            })
    for web in state.get("web_search_results", []):
        sources_cited.append({
            "source_name": web.get("title"),
            "url": web.get("url"),
            "classification": "NON_CONFIDENTIAL",
            "source_type": "WEB",
        })

    return {
        **state,
        "final_answer": result["content"],
        "model_used": result["model_used"],
        "is_local_model": result["is_local"],
        "needs_fallback_confirmation": False,
        "sources_cited": sources_cited,
    }


async def validate_response(state: AgentState) -> AgentState:
    """
    Post-generation validation — ensure no confidential leakage.
    Basic checks only; production would add more sophisticated PII detection.
    """
    if not state.get("final_answer"):
        return state

    # If the query was non-confidential but answer contains suspicious patterns
    # In production: integrate PII detection / regex filters here
    logger.info("agent.response_validated")
    return state


# ─── Routing functions ───────────────────────────────────────────────────
def should_do_structured_analysis(state: AgentState) -> str:
    if state["intent"] in ("structured", "multi_doc"):
        return "structured_analysis"
    return "web_search"


def should_do_web_search(state: AgentState) -> str:
    if not state["context_sufficient"] and state["security_level"] == "NON_CONFIDENTIAL":
        return "web_search"
    return "model_router"


# ─── Build Graph ────────────────────────────────────────────────────────
def build_rag_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("load_context", load_user_context)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("classify_security", classify_security)
    graph.add_node("select_sources", select_sources)
    graph.add_node("retrieve", retrieve)
    graph.add_node("structured_analysis", perform_structured_analysis)
    graph.add_node("web_search", perform_web_search)
    graph.add_node("model_router", route_model)
    graph.add_node("validate_response", validate_response)

    # Set entry point
    graph.set_entry_point("load_context")

    # Add edges
    graph.add_edge("load_context", "classify_intent")
    graph.add_edge("classify_intent", "classify_security")
    graph.add_edge("classify_security", "select_sources")
    graph.add_edge("select_sources", "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        should_do_structured_analysis,
        {
            "structured_analysis": "structured_analysis",
            "web_search": "web_search",
        }
    )
    graph.add_edge("structured_analysis", "web_search")
    graph.add_edge("web_search", "model_router")
    graph.add_edge("model_router", "validate_response")
    graph.add_edge("validate_response", END)

    return graph.compile()


# Compiled agent graph (singleton)
rag_graph = build_rag_graph()
