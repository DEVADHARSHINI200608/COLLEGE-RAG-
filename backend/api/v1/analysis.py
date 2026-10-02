"""
Multi-document analysis routes — deterministic comparison, counting, matching.
"""
from __future__ import annotations

import io
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.rbac import Permission, require_permission
from database.connection import get_db
from database.models import User
from tools.data_analysis import analyzer, load_dataframe

router = APIRouter(prefix="/analysis", tags=["analysis"])


class ResponseAnalysisResult(BaseModel):
    total_students: int
    yes_count: int
    no_count: int
    no_response_count: int
    yes_students: List[str]
    no_students: List[str]
    no_response_students: List[str]


class MissingResponseResult(BaseModel):
    total: int
    responded: int
    missing_count: int
    missing_names: List[str]


@router.post("/missing-responses", response_model=MissingResponseResult)
async def detect_missing_responses(
    master_file: UploadFile = File(..., description="CSV/Excel with master student list"),
    response_file: UploadFile = File(..., description="CSV/Excel with form responses"),
    master_name_col: str = Form("Name"),
    response_name_col: str = Form("Name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Detect students in master list who have NOT responded.
    DETERMINISTIC — no LLM involved in the counting.
    Requires FACULTY or ADMIN role.
    """
    require_permission(current_user.role, Permission.VIEW_MISSING_RESPONSES)

    master_bytes = await master_file.read()
    response_bytes = await response_file.read()

    try:
        master_df = load_dataframe(master_bytes, master_file.filename or "master.csv")
        response_df = load_dataframe(response_bytes, response_file.filename or "responses.csv")
    except Exception as exc:
        raise HTTPException(400, f"Failed to read files: {exc}")

    if master_name_col not in master_df.columns:
        raise HTTPException(400, f"Column '{master_name_col}' not found in master file. "
                                f"Available: {list(master_df.columns)}")
    if response_name_col not in response_df.columns:
        raise HTTPException(400, f"Column '{response_name_col}' not found in response file. "
                                f"Available: {list(response_df.columns)}")

    result = analyzer.detect_missing(master_df, response_df, master_name_col, response_name_col)
    return MissingResponseResult(**result)


@router.post("/responses", response_model=ResponseAnalysisResult)
async def analyze_responses(
    master_file: UploadFile = File(...),
    response_file: UploadFile = File(...),
    master_name_col: str = Form("Name"),
    response_name_col: str = Form("Name"),
    response_col: str = Form("Response"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Full Yes/No/Missing analysis.
    Example: Document 2 = master list, Document 1 = form responses.
    Returns exact counts of Yes, No, and No Response.
    """
    require_permission(current_user.role, Permission.ANALYZE_STUDENT_RESPONSES)

    master_bytes = await master_file.read()
    response_bytes = await response_file.read()

    try:
        master_df = load_dataframe(master_bytes, master_file.filename or "master.csv")
        response_df = load_dataframe(response_bytes, response_file.filename or "responses.csv")
    except Exception as exc:
        raise HTTPException(400, f"Failed to read files: {exc}")

    for col, df, fname in [
        (master_name_col, master_df, "master file"),
        (response_name_col, response_df, "response file"),
        (response_col, response_df, "response file"),
    ]:
        if col not in df.columns:
            raise HTTPException(400, f"Column '{col}' not found in {fname}.")

    result = analyzer.analyze_responses(
        master_list_df=master_df,
        response_df=response_df,
        name_col_master=master_name_col,
        name_col_response=response_name_col,
        response_col=response_col,
    )
    return ResponseAnalysisResult(**result)


@router.post("/compare-lists")
async def compare_lists(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
    col_a: str = Form("Name"),
    col_b: str = Form("Name"),
    current_user: User = Depends(get_current_user),
):
    """Compare two lists — find items only in A, only in B, and in both."""
    require_permission(current_user.role, Permission.COMPARE_STUDENT_LISTS)

    bytes_a = await file_a.read()
    bytes_b = await file_b.read()

    df_a = load_dataframe(bytes_a, file_a.filename or "list_a.csv")
    df_b = load_dataframe(bytes_b, file_b.filename or "list_b.csv")

    return analyzer.compare_lists(df_a, df_b, col_a, col_b)
