"""
Chat / Ask AI routes — main interface for RAG queries.
Handles the fallback confirmation flow (sections 19-22).
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import rag_graph, AgentState
from auth.dependencies import get_current_user
from database.connection import get_db
from database.models import ChatSession, ChatMessage, User
from models.router import RouterResult

router = APIRouter(prefix="/chat", tags=["chat"])


class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    source_ids: Optional[List[str]] = None  # Optionally pin specific sources
    force_local_model: bool = False          # Set to True after user confirms fallback


class SourceCited(BaseModel):
    source_name: Optional[str]
    source_id: Optional[str] = None
    classification: Optional[str] = None
    url: Optional[str] = None
    source_type: Optional[str] = None


class QueryResponse(BaseModel):
    answer: Optional[str]
    session_id: str
    message_id: str
    model_used: Optional[str]
    is_local_model: bool
    sources: List[SourceCited]
    needs_fallback_confirmation: bool
    fallback_reason: Optional[str]
    error: Optional[str] = None


@router.post("/query", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Main Ask AI endpoint.
    
    If the external LLM is unavailable, returns needs_fallback_confirmation=True.
    The frontend must then show the fallback confirmation modal,
    and re-call this endpoint with force_local_model=True if user confirms.
    """
    if not body.query.strip():
        raise HTTPException(400, "Query cannot be empty.")

    # Get or create session
    session_id = body.session_id
    if not session_id:
        session = ChatSession(user_id=str(current_user.id))
        db.add(session)
        await db.flush()
        session_id = str(session.id)
    else:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == str(current_user.id),
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(404, "Session not found.")

    # Build initial state
    initial_state: AgentState = {
        "query": body.query,
        "user_id": str(current_user.id),
        "user_role": current_user.role,
        "user_department": current_user.department,
        "session_id": session_id,
        "force_local_model": body.force_local_model,
        "intent": None,
        "security_level": None,
        "authorized_source_ids": [],
        "selected_source_ids": body.source_ids or [],
        "retrieved_docs": [],
        "structured_results": None,
        "web_search_results": [],
        "context_sufficient": False,
        "needs_fallback_confirmation": False,
        "fallback_reason": None,
        "model_used": None,
        "is_local_model": False,
        "final_answer": None,
        "sources_cited": [],
        "error": None,
        "db": db,
    }

    # Run agent graph
    try:
        final_state = await rag_graph.ainvoke(initial_state)
    except Exception as exc:
        raise HTTPException(500, f"Agent error: {str(exc)}")

    # Save user message
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=body.query,
    )
    db.add(user_msg)
    await db.flush()

    # Save assistant message (if we have an answer)
    message_id = str(uuid.uuid4())
    if final_state.get("final_answer"):
        assistant_msg = ChatMessage(
            id=message_id,
            session_id=session_id,
            role="assistant",
            content=final_state["final_answer"],
            sources_used=final_state.get("sources_cited", []),
            model_used=final_state.get("model_used"),
            is_local_model=final_state.get("is_local_model", False),
        )
        db.add(assistant_msg)

    return QueryResponse(
        answer=final_state.get("final_answer"),
        session_id=session_id,
        message_id=message_id,
        model_used=final_state.get("model_used"),
        is_local_model=final_state.get("is_local_model", False),
        sources=[SourceCited(**s) for s in final_state.get("sources_cited", [])],
        needs_fallback_confirmation=final_state.get("needs_fallback_confirmation", False),
        fallback_reason=final_state.get("fallback_reason"),
        error=final_state.get("error"),
    )


@router.get("/history/{session_id}")
async def get_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == str(current_user.id),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found.")

    msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = msg_result.scalars().all()

    return {
        "session_id": session_id,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "model_used": m.model_used,
                "is_local_model": m.is_local_model,
                "sources": m.sources_used or [],
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.get("/model-status")
async def model_status(current_user: User = Depends(get_current_user)):
    """Get current AI model mode (external/local)."""
    from models.router import model_router, ModelMode
    return {
        "mode": model_router.current_mode.value,
        "is_local": model_router.current_mode == ModelMode.LOCAL,
        "local_available": await model_router.check_local_availability(),
    }
