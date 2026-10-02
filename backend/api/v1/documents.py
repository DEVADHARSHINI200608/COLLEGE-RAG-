"""
Document upload and management routes.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.rbac import Permission, require_permission
from database.connection import get_db
from database.models import Source, SourceStatus, User
from ingestion.pipeline import ingest_file, validate_file, SUPPORTED_EXTENSIONS
from security.audit import log_event
from config import settings

router = APIRouter(prefix="/documents", tags=["documents"])


class SourceResponse(BaseModel):
    id: str
    source_name: str
    source_type: str
    classification: str
    is_standard_resource: bool
    is_student_uploaded: bool
    status: str
    chunk_count: int
    file_size_bytes: Optional[int]
    department: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    files: List[UploadFile] = File(...),
    source_name: str = Form(...),
    classification: str = Form("NON_CONFIDENTIAL"),
    is_standard_resource: bool = Form(False),
    department: Optional[str] = Form(None),
    access_roles: Optional[str] = Form(None),  # JSON array as string
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload one or more documents."""
    import json

    # Permission checks
    if classification == "CONFIDENTIAL":
        require_permission(current_user.role, Permission.UPLOAD_CONFIDENTIAL)
    if is_standard_resource:
        require_permission(current_user.role, Permission.UPLOAD_STANDARD_RESOURCE)

    if len(files) > settings.MAX_UPLOAD_FILES_PER_REQUEST:
        raise HTTPException(400, f"Max {settings.MAX_UPLOAD_FILES_PER_REQUEST} files per upload.")

    parsed_roles = json.loads(access_roles) if access_roles else []
    results = []

    for file in files:
        file_bytes = await file.read()
        filename = file.filename or "unknown"

        # Validate
        ok, msg = validate_file(filename, file_bytes)
        if not ok:
            results.append({"filename": filename, "status": "error", "message": msg})
            continue

        # Save file
        source_id = str(uuid.uuid4())
        ext = Path(filename).suffix.lower()
        save_dir = Path(settings.FILE_UPLOAD_DIR) / current_user.id
        save_dir.mkdir(parents=True, exist_ok=True)
        file_path = save_dir / f"{source_id}{ext}"
        file_path.write_bytes(file_bytes)

        # Create DB record
        source_type = ext.lstrip(".").upper()
        source = Source(
            id=source_id,
            source_name=source_name or filename,
            source_type=source_type,
            classification=classification,
            is_standard_resource=is_standard_resource,
            is_student_uploaded=(current_user.role == "STUDENT"),
            owner_id=str(current_user.id),
            uploaded_by=str(current_user.id),
            department=department,
            access_roles=parsed_roles,
            file_path=str(file_path),
            file_size_bytes=len(file_bytes),
            status=SourceStatus.PROCESSING,
        )
        db.add(source)
        await db.flush()

        # Ingest (parse → chunk → embed)
        try:
            chunk_count, content_hash = await ingest_file(
                filename=filename,
                file_bytes=file_bytes,
                source_id=source_id,
                source_name=source_name or filename,
                classification=classification,
                access_roles=parsed_roles,
                allowed_users=[],
                allowed_departments=[department] if department else [],
            )
            source.chunk_count = chunk_count
            source.content_hash = content_hash
            source.status = SourceStatus.ACTIVE
            results.append({
                "filename": filename,
                "source_id": source_id,
                "status": "success",
                "chunks": chunk_count,
            })
        except Exception as exc:
            source.status = SourceStatus.FAILED
            results.append({"filename": filename, "status": "error", "message": str(exc)})

    await log_event(db, "DOCUMENT_UPLOAD", user_id=str(current_user.id),
                    details={"files": [r["filename"] for r in results]})

    return {"results": results}


@router.get("/", response_model=List[SourceResponse])
async def list_documents(
    classification: Optional[str] = None,
    is_standard_resource: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents accessible to the current user."""
    query = select(Source).where(Source.status != "DELETED")

    # Students only see non-confidential
    if current_user.role == "STUDENT":
        query = query.where(Source.classification == "NON_CONFIDENTIAL")
    elif classification:
        query = query.where(Source.classification == classification)

    if is_standard_resource is not None:
        query = query.where(Source.is_standard_resource == is_standard_resource)

    result = await db.execute(query)
    sources = result.scalars().all()

    # Source-level auth filter
    authorized = []
    for src in sources:
        access_roles = src.access_roles or []
        if not access_roles or current_user.role in access_roles:
            authorized.append(src)

    return [
        SourceResponse(
            id=str(s.id),
            source_name=s.source_name,
            source_type=s.source_type,
            classification=s.classification,
            is_standard_resource=s.is_standard_resource,
            is_student_uploaded=s.is_student_uploaded,
            status=s.status,
            chunk_count=s.chunk_count or 0,
            file_size_bytes=s.file_size_bytes,
            department=s.department,
            created_at=s.created_at.isoformat(),
        )
        for s in authorized
    ]


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    source_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Document not found.")

    # Authorization: owners can delete their own; admin can delete any
    if current_user.role != "ADMIN" and str(source.uploaded_by) != str(current_user.id):
        raise HTTPException(403, "Not authorized to delete this document.")

    source.status = SourceStatus.DELETED
    await log_event(db, "DOCUMENT_DELETE", user_id=str(current_user.id),
                    resource_id=source_id)
