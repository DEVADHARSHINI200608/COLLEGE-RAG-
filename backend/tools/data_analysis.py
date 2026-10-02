"""
Data Analysis Tool — deterministic, programmatic analysis.
Used for counting, matching, comparison — NOT relying on LLM for exact numbers.
"""
from __future__ import annotations

import io
from typing import Dict, List, Optional, Set, Tuple, Any

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def normalize_name(name: str) -> str:
    """Normalize a name for matching: lowercase, strip whitespace."""
    return str(name).strip().lower()


def load_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Load CSV or Excel into a DataFrame."""
    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_bytes))
    return pd.read_csv(io.BytesIO(file_bytes))


class MultiDocumentAnalyzer:
    """
    Deterministic analysis engine for multi-document questions.
    All counting/matching logic is programmatic — not LLM-guessed.
    """

    def analyze_responses(
        self,
        master_list_df: pd.DataFrame,
        response_df: pd.DataFrame,
        name_col_master: str,
        name_col_response: str,
        response_col: str,
        yes_values: Optional[List[str]] = None,
        no_values: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Core analysis:
        - master_list_df: all students
        - response_df: students who responded (with Yes/No column)

        Returns structured result with counts and lists.
        """
        yes_values = [v.lower() for v in (yes_values or ["yes", "y", "1", "true"])]
        no_values = [v.lower() for v in (no_values or ["no", "n", "0", "false"])]

        # Normalize names
        master_names: Set[str] = {
            normalize_name(n) for n in master_list_df[name_col_master].dropna()
        }

        # Build response map: normalized_name → response
        response_map: Dict[str, str] = {}
        for _, row in response_df.iterrows():
            name = normalize_name(row[name_col_response])
            response = str(row[response_col]).strip().lower()
            response_map[name] = response

        # Categorize
        yes_students: List[str] = []
        no_students: List[str] = []
        no_response_students: List[str] = []

        for orig_name in master_list_df[name_col_master].dropna():
            norm = normalize_name(orig_name)
            display = str(orig_name).strip()

            if norm not in response_map:
                no_response_students.append(display)
            elif response_map[norm] in yes_values:
                yes_students.append(display)
            elif response_map[norm] in no_values:
                no_students.append(display)
            else:
                no_response_students.append(display)  # unknown response → treat as missing

        return {
            "total_students": len(master_names),
            "yes_count": len(yes_students),
            "no_count": len(no_students),
            "no_response_count": len(no_response_students),
            "yes_students": yes_students,
            "no_students": no_students,
            "no_response_students": no_response_students,
        }

    def compare_lists(
        self,
        list_a_df: pd.DataFrame,
        list_b_df: pd.DataFrame,
        col_a: str,
        col_b: str,
    ) -> Dict[str, Any]:
        """Find items in A not in B, in B not in A, and in both."""
        set_a = {normalize_name(n) for n in list_a_df[col_a].dropna()}
        set_b = {normalize_name(n) for n in list_b_df[col_b].dropna()}

        only_in_a = sorted(set_a - set_b)
        only_in_b = sorted(set_b - set_a)
        in_both = sorted(set_a & set_b)

        return {
            "only_in_a": only_in_a,
            "only_in_b": only_in_b,
            "in_both": in_both,
            "count_only_in_a": len(only_in_a),
            "count_only_in_b": len(only_in_b),
            "count_in_both": len(in_both),
        }

    def find_duplicates(self, df: pd.DataFrame, col: str) -> Dict[str, Any]:
        """Find duplicate entries in a column."""
        normalized = df[col].dropna().apply(normalize_name)
        duplicates = normalized[normalized.duplicated(keep=False)]
        return {
            "has_duplicates": not duplicates.empty,
            "duplicate_names": sorted(duplicates.unique().tolist()),
            "duplicate_count": len(duplicates.unique()),
        }

    def count_values(
        self,
        df: pd.DataFrame,
        col: str,
        target_value: str,
    ) -> int:
        """Count rows where col matches target_value (case-insensitive)."""
        return int(
            df[col].apply(lambda x: normalize_name(str(x)) == normalize_name(target_value)).sum()
        )

    def detect_missing(
        self,
        master_df: pd.DataFrame,
        response_df: pd.DataFrame,
        master_col: str,
        response_col: str,
    ) -> Dict[str, Any]:
        """Find people in master list who are NOT in response list."""
        master_names = {normalize_name(n) for n in master_df[master_col].dropna()}
        responded_names = {normalize_name(n) for n in response_df[response_col].dropna()}

        missing_norm = master_names - responded_names
        # Get original (non-normalized) names for display
        missing_display = [
            str(n).strip()
            for n in master_df[master_col].dropna()
            if normalize_name(n) in missing_norm
        ]

        return {
            "total": len(master_names),
            "responded": len(responded_names),
            "missing_count": len(missing_norm),
            "missing_names": missing_display,
        }


# Singleton
analyzer = MultiDocumentAnalyzer()
