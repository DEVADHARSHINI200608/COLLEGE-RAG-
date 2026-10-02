"""
Platform test suite — covers all requirements from section 49.
Tests are structured so they can run without external APIs or vector DBs.
"""
from __future__ import annotations

import io
import os
import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# ── Point to backend root so imports work ───────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Set minimal env before importing config
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_rag_platform.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-characters-long!!")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-chars-long!!")
os.environ.setdefault("EMBEDDING_PROVIDER", "sentence_transformers")
os.environ.setdefault("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
os.environ.setdefault("EXTERNAL_LLM_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("LOCAL_LLM_ENABLED", "true")
os.environ.setdefault("SCHEDULER_ENABLED", "false")   # Don't start scheduler in tests
os.environ.setdefault("WEB_SEARCH_ENABLED", "false")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# ════════════════════════════════════════════════════════════════════════
# SECTION A — UNIT TESTS (no server/DB needed)
# ════════════════════════════════════════════════════════════════════════

class TestRBAC:
    """Requirements: RBAC, role permissions (Section 3, 32)"""

    def test_student_has_educational_rag_permission(self):
        from auth.rbac import has_permission, Permission
        assert has_permission("STUDENT", Permission.USE_EDUCATIONAL_RAG)

    def test_student_cannot_access_confidential(self):
        from auth.rbac import has_permission, Permission
        assert not has_permission("STUDENT", Permission.ACCESS_CONFIDENTIAL)

    def test_student_cannot_manage_users(self):
        from auth.rbac import has_permission, Permission
        assert not has_permission("STUDENT", Permission.MANAGE_USERS)

    def test_student_can_upload_own_material(self):
        from auth.rbac import has_permission, Permission
        assert has_permission("STUDENT", Permission.UPLOAD_OWN_MATERIAL)

    def test_faculty_can_upload_confidential(self):
        from auth.rbac import has_permission, Permission
        assert has_permission("FACULTY", Permission.UPLOAD_CONFIDENTIAL)

    def test_faculty_can_set_deadlines(self):
        from auth.rbac import has_permission, Permission
        assert has_permission("FACULTY", Permission.SET_DEADLINES)

    def test_faculty_can_analyze_responses(self):
        from auth.rbac import has_permission, Permission
        assert has_permission("FACULTY", Permission.ANALYZE_STUDENT_RESPONSES)

    def test_faculty_cannot_manage_users(self):
        from auth.rbac import has_permission, Permission
        assert not has_permission("FACULTY", Permission.MANAGE_USERS)

    def test_admin_has_all_permissions(self):
        from auth.rbac import has_permission, Permission
        for p in Permission:
            assert has_permission("ADMIN", p), f"Admin missing: {p}"

    def test_unknown_role_has_zero_permissions(self):
        from auth.rbac import get_permissions
        assert len(get_permissions("UNKNOWN")) == 0

    def test_require_permission_raises_403(self):
        from auth.rbac import require_permission, Permission
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            require_permission("STUDENT", Permission.MANAGE_USERS)
        assert exc.value.status_code == 403


class TestJWT:
    """Requirements: Authentication (Section 5, 32)"""

    def test_create_and_verify_access_token(self):
        from auth.jwt_handler import create_access_token, verify_access_token
        token = create_access_token({"sub": "user-123", "role": "STUDENT"})
        payload = verify_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["role"] == "STUDENT"
        assert payload["type"] == "access"

    def test_refresh_token_type(self):
        from auth.jwt_handler import create_refresh_token, verify_refresh_token
        token = create_refresh_token({"sub": "user-123"})
        payload = verify_refresh_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_access_token_cannot_be_used_as_refresh(self):
        from auth.jwt_handler import create_access_token, verify_refresh_token
        token = create_access_token({"sub": "user-123"})
        assert verify_refresh_token(token) is None

    def test_invalid_token_returns_none(self):
        from auth.jwt_handler import verify_access_token
        assert verify_access_token("not.a.real.token") is None

    def test_tampered_token_returns_none(self):
        from auth.jwt_handler import create_access_token, verify_access_token
        token = create_access_token({"sub": "user-123"})
        tampered = token[:-5] + "XXXXX"
        assert verify_access_token(tampered) is None


class TestIngestionPipeline:
    """Requirements: Multi-format ingestion (Section 4, 13, Phase 2)"""

    def test_validate_pdf_supported(self):
        from ingestion.pipeline import validate_file
        ok, msg = validate_file("test.pdf", b"x" * 100)
        assert ok, msg

    def test_validate_docx_supported(self):
        from ingestion.pipeline import validate_file
        ok, msg = validate_file("notes.docx", b"x" * 100)
        assert ok, msg

    def test_validate_pptx_supported(self):
        from ingestion.pipeline import validate_file
        ok, msg = validate_file("slides.pptx", b"x" * 100)
        assert ok, msg

    def test_validate_csv_supported(self):
        from ingestion.pipeline import validate_file
        ok, msg = validate_file("data.csv", b"x" * 100)
        assert ok, msg

    def test_validate_xlsx_supported(self):
        from ingestion.pipeline import validate_file
        ok, msg = validate_file("spreadsheet.xlsx", b"x" * 100)
        assert ok, msg

    def test_validate_txt_supported(self):
        from ingestion.pipeline import validate_file
        ok, msg = validate_file("notes.txt", b"x" * 100)
        assert ok, msg

    def test_validate_md_supported(self):
        from ingestion.pipeline import validate_file
        ok, msg = validate_file("readme.md", b"x" * 100)
        assert ok, msg

    def test_validate_unsupported_type(self):
        from ingestion.pipeline import validate_file
        ok, msg = validate_file("virus.exe", b"x" * 100)
        assert not ok
        assert "Unsupported" in msg

    def test_validate_file_too_large(self):
        from ingestion.pipeline import validate_file
        big = b"x" * (51 * 1024 * 1024)  # 51 MB
        ok, msg = validate_file("large.pdf", big)
        assert not ok
        assert "large" in msg.lower() or "max" in msg.lower()

    def test_parse_txt(self):
        from ingestion.pipeline import parse_txt
        result = parse_txt(b"Hello, World!", "test.txt")
        assert "Hello, World!" in result

    def test_parse_csv_as_text(self):
        from ingestion.pipeline import parse_csv
        csv_bytes = b"Name,Response\nAlice,Yes\nBob,No\n"
        result = parse_csv(csv_bytes, "data.csv")
        assert "Alice" in result
        assert "Yes" in result

    def test_parse_xlsx_as_text(self):
        from ingestion.pipeline import parse_xlsx
        import openpyxl, io
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Name", "Score"])
        ws.append(["Alice", 90])
        buf = io.BytesIO()
        wb.save(buf)
        result = parse_xlsx(buf.getvalue(), "scores.xlsx")
        assert "Alice" in result

    def test_content_hash_is_deterministic(self):
        from ingestion.pipeline import compute_hash
        data = b"hello world"
        assert compute_hash(data) == compute_hash(data)

    def test_different_content_different_hash(self):
        from ingestion.pipeline import compute_hash
        assert compute_hash(b"abc") != compute_hash(b"xyz")

    def test_chunk_text_splits_large_text(self):
        from ingestion.pipeline import chunk_text
        big_text = "This is a sentence. " * 300
        chunks = chunk_text(big_text, {"source_id": "test-src"})
        assert len(chunks) > 1

    def test_chunk_text_preserves_metadata(self):
        from ingestion.pipeline import chunk_text
        chunks = chunk_text("Hello world " * 100, {"source_id": "abc", "filename": "test.txt"})
        for c in chunks:
            assert c.metadata["source_id"] == "abc"


class TestDataAnalysis:
    """Requirements: Deterministic multi-doc analysis (Sections 11, 12, 13)"""

    def _master(self):
        import pandas as pd
        return pd.DataFrame({"Name": ["Arun", "Priya", "Karthik", "Divya", "Rahul"]})

    def _responses(self):
        import pandas as pd
        return pd.DataFrame({
            "Name": ["Arun", "Priya", "Karthik"],
            "Response": ["Yes", "No", "Yes"]
        })

    def test_yes_count_exact(self):
        from tools.data_analysis import analyzer
        r = analyzer.analyze_responses(self._master(), self._responses(), "Name", "Name", "Response")
        assert r["yes_count"] == 2

    def test_no_count_exact(self):
        from tools.data_analysis import analyzer
        r = analyzer.analyze_responses(self._master(), self._responses(), "Name", "Name", "Response")
        assert r["no_count"] == 1

    def test_no_response_count_exact(self):
        from tools.data_analysis import analyzer
        r = analyzer.analyze_responses(self._master(), self._responses(), "Name", "Name", "Response")
        assert r["no_response_count"] == 2

    def test_total_students_correct(self):
        from tools.data_analysis import analyzer
        r = analyzer.analyze_responses(self._master(), self._responses(), "Name", "Name", "Response")
        assert r["total_students"] == 5

    def test_missing_names_correct(self):
        from tools.data_analysis import analyzer
        r = analyzer.analyze_responses(self._master(), self._responses(), "Name", "Name", "Response")
        assert set(r["no_response_students"]) == {"Divya", "Rahul"}

    def test_yes_students_correct(self):
        from tools.data_analysis import analyzer
        r = analyzer.analyze_responses(self._master(), self._responses(), "Name", "Name", "Response")
        assert set(r["yes_students"]) == {"Arun", "Karthik"}

    def test_name_normalization_case_insensitive(self):
        import pandas as pd
        from tools.data_analysis import analyzer
        master = pd.DataFrame({"Name": ["ARUN", "PRIYA"]})
        resp = pd.DataFrame({"Name": ["arun", "priya"], "Response": ["Yes", "No"]})
        r = analyzer.analyze_responses(master, resp, "Name", "Name", "Response")
        assert r["yes_count"] == 1
        assert r["no_count"] == 1
        assert r["no_response_count"] == 0

    def test_name_normalization_whitespace(self):
        import pandas as pd
        from tools.data_analysis import analyzer
        master = pd.DataFrame({"Name": ["  Arun  ", " Priya"]})
        resp = pd.DataFrame({"Name": ["Arun", "Priya"], "Response": ["Yes", "No"]})
        r = analyzer.analyze_responses(master, resp, "Name", "Name", "Response")
        assert r["yes_count"] == 1
        assert r["no_response_count"] == 0

    def test_detect_missing_responses(self):
        import pandas as pd
        from tools.data_analysis import analyzer
        master = pd.DataFrame({"Name": ["Alice", "Bob", "Charlie"]})
        responded = pd.DataFrame({"Name": ["Alice"]})
        r = analyzer.detect_missing(master, responded, "Name", "Name")
        assert r["missing_count"] == 2
        assert set(r["missing_names"]) == {"Bob", "Charlie"}
        assert r["total"] == 3
        assert r["responded"] == 1

    def test_compare_lists_only_in_a(self):
        import pandas as pd
        from tools.data_analysis import analyzer
        a = pd.DataFrame({"Name": ["Alice", "Bob", "Charlie"]})
        b = pd.DataFrame({"Name": ["Alice", "David"]})
        r = analyzer.compare_lists(a, b, "Name", "Name")
        assert set(r["only_in_a"]) == {"bob", "charlie"}

    def test_compare_lists_only_in_b(self):
        import pandas as pd
        from tools.data_analysis import analyzer
        a = pd.DataFrame({"Name": ["Alice"]})
        b = pd.DataFrame({"Name": ["Alice", "David"]})
        r = analyzer.compare_lists(a, b, "Name", "Name")
        assert "david" in r["only_in_b"]

    def test_compare_lists_in_both(self):
        import pandas as pd
        from tools.data_analysis import analyzer
        a = pd.DataFrame({"Name": ["Alice", "Bob"]})
        b = pd.DataFrame({"Name": ["Alice", "Charlie"]})
        r = analyzer.compare_lists(a, b, "Name", "Name")
        assert "alice" in r["in_both"]

    def test_find_duplicates(self):
        import pandas as pd
        from tools.data_analysis import analyzer
        df = pd.DataFrame({"Name": ["Alice", "alice", "Bob"]})
        r = analyzer.find_duplicates(df, "Name")
        assert r["has_duplicates"]
        assert "alice" in r["duplicate_names"]

    def test_no_duplicates(self):
        import pandas as pd
        from tools.data_analysis import analyzer
        df = pd.DataFrame({"Name": ["Alice", "Bob", "Charlie"]})
        r = analyzer.find_duplicates(df, "Name")
        assert not r["has_duplicates"]

    def test_count_values(self):
        import pandas as pd
        from tools.data_analysis import analyzer
        df = pd.DataFrame({"Response": ["Yes", "No", "Yes", "yes", "YES"]})
        count = analyzer.count_values(df, "Response", "Yes")
        assert count == 4  # case-insensitive: Yes, Yes, yes, YES — "No" excluded

    def test_all_responded_no_missing(self):
        import pandas as pd
        from tools.data_analysis import analyzer
        master = pd.DataFrame({"Name": ["A", "B"]})
        resp = pd.DataFrame({"Name": ["A", "B"], "Response": ["Yes", "Yes"]})
        r = analyzer.analyze_responses(master, resp, "Name", "Name", "Response")
        assert r["no_response_count"] == 0
        assert r["yes_count"] == 2


class TestModelRouter:
    """Requirements: ModelRouter, fallback, local LLM (Sections 17-24, 45-46)"""

    def test_quota_error_detection(self):
        from models.router import _is_quota_error
        assert _is_quota_error(Exception("quota exceeded"))
        assert _is_quota_error(Exception("rate limit reached"))
        assert _is_quota_error(Exception("insufficient_quota"))
        assert _is_quota_error(Exception("429 Too Many Requests"))
        assert _is_quota_error(Exception("billing limit"))

    def test_non_api_error_not_detected_as_quota(self):
        from models.router import _is_quota_error
        assert not _is_quota_error(ValueError("Invalid PDF format"))
        assert not _is_quota_error(FileNotFoundError("file not found"))
        assert not _is_quota_error(KeyError("missing key"))

    @pytest.mark.asyncio
    async def test_external_failure_returns_needs_fallback(self):
        """Req: API failure must return NEEDS_FALLBACK, not raise exception"""
        from models.router import ModelRouter, RouterResult
        router = ModelRouter()
        with patch.object(router.external, 'ainvoke',
                          AsyncMock(side_effect=Exception("quota exceeded for your account"))):
            result = await router.generate(
                messages=[{"role": "user", "content": "test"}],
                db=None
            )
        assert result["status"] == RouterResult.NEEDS_FALLBACK
        assert result["needs_fallback_confirmation"] is True
        assert result["content"] is None

    @pytest.mark.asyncio
    async def test_invalid_pdf_does_not_trigger_fallback(self):
        """Req Section 46: Invalid PDF must NOT trigger fallback"""
        from ingestion.pipeline import validate_file
        ok, msg = validate_file("corrupt.pdf", b"not a real pdf but valid ext")
        # Validation error is a value error — not an API quota error
        from models.router import _is_quota_error
        assert not _is_quota_error(ValueError(msg))

    @pytest.mark.asyncio
    async def test_force_local_uses_local_model(self):
        """Req: force_local=True must route to local LLM"""
        from models.router import ModelRouter, RouterResult, ModelMode
        router = ModelRouter()
        with patch.object(router.local, 'ainvoke',
                          AsyncMock(return_value=("Local answer", 10, 20))):
            result = await router.generate(
                messages=[{"role": "user", "content": "test"}],
                db=None,
                force_local=True
            )
        assert result["status"] == RouterResult.SUCCESS
        assert result["is_local"] is True
        assert "Local answer" in result["content"]
        assert router.current_mode == ModelMode.LOCAL

    @pytest.mark.asyncio
    async def test_successful_external_returns_success(self):
        from models.router import ModelRouter, RouterResult, ModelMode
        router = ModelRouter()
        with patch.object(router.external, 'ainvoke',
                          AsyncMock(return_value=("External answer", 50, 100))):
            result = await router.generate(
                messages=[{"role": "user", "content": "hello"}],
                db=None
            )
        assert result["status"] == RouterResult.SUCCESS
        assert result["is_local"] is False
        assert "External answer" in result["content"]

    def test_local_disabled_returns_error(self):
        from models.router import ModelRouter, RouterResult
        import asyncio
        router = ModelRouter()
        with patch("models.router.settings") as mock_settings:
            mock_settings.LOCAL_LLM_ENABLED = False
            mock_settings.LOCAL_LLM_PROVIDER = "ollama"
            mock_settings.OLLAMA_MODEL = "llama3.2"
            result = asyncio.run(router._generate_local(
                [{"role": "user", "content": "test"}]
            ))
        assert result["status"] == RouterResult.ERROR


class TestUsageMonitor:
    """Requirements: Usage monitoring (Sections 18, 36, 37)"""

    def test_estimate_cost_openai(self):
        from monitoring.usage_tracker import estimate_cost
        cost = estimate_cost("openai", "gpt-4o-mini", 1000)
        assert cost == pytest.approx(0.00015, rel=0.01)

    def test_estimate_cost_local_is_zero(self):
        from monitoring.usage_tracker import estimate_cost
        assert estimate_cost("ollama", "llama3.2", 9999) == 0.0

    def test_role_multipliers(self):
        from monitoring.usage_tracker import get_role_limit_multiplier
        assert get_role_limit_multiplier("STUDENT") < get_role_limit_multiplier("FACULTY")
        assert get_role_limit_multiplier("FACULTY") < get_role_limit_multiplier("ADMIN")

    def test_unknown_role_gets_student_limit(self):
        from monitoring.usage_tracker import get_role_limit_multiplier
        assert get_role_limit_multiplier("UNKNOWN") == get_role_limit_multiplier("STUDENT")


class TestSecurityBoundaries:
    """Requirements: Security classification, no prompt-only security (Section 6, 34)"""

    def test_confidential_classification_enum(self):
        from database.models import Classification
        assert Classification.CONFIDENTIAL == "CONFIDENTIAL"
        assert Classification.NON_CONFIDENTIAL == "NON_CONFIDENTIAL"

    def test_source_type_enum_coverage(self):
        from database.models import SourceType
        required = {"PDF", "CSV", "XLSX", "DOC", "DOCX", "PPT", "PPTX", "TXT", "MARKDOWN"}
        actual = {t.value for t in SourceType}
        assert required.issubset(actual), f"Missing: {required - actual}"

    def test_user_role_enum(self):
        from database.models import UserRole
        assert "STUDENT" in [r.value for r in UserRole]
        assert "FACULTY" in [r.value for r in UserRole]
        assert "ADMIN" in [r.value for r in UserRole]

    def test_api_status_covers_all_failure_types(self):
        from database.models import APIStatus
        statuses = {s.value for s in APIStatus}
        assert "RATE_LIMITED" in statuses
        assert "QUOTA_EXCEEDED" in statuses
        assert "BUDGET_EXCEEDED" in statuses
        assert "API_UNAVAILABLE" in statuses
        assert "TIMEOUT" in statuses
        assert "LOCAL_FALLBACK" in statuses

    def test_no_secrets_hardcoded_in_config(self):
        """Req Section 35: API keys must come from env, not be hardcoded"""
        import inspect
        import config as cfg_module
        source = inspect.getsource(cfg_module)
        # Ensure no real-looking API keys are hardcoded
        import re
        # sk- prefix is OpenAI format
        assert not re.search(r'sk-[A-Za-z0-9]{20,}', source), "Hardcoded OpenAI key found!"
        assert "CHANGE-ME" in source or "your-" in source  # placeholder pattern


class TestSettings:
    """Requirements: Configuration (Section 35, 36, 48)"""

    def test_settings_load_from_env(self):
        from config import settings
        assert settings.DATABASE_URL is not None
        assert settings.JWT_SECRET_KEY is not None

    def test_max_file_size_property(self):
        from config import settings
        assert settings.max_file_size_bytes == settings.MAX_FILE_SIZE_MB * 1024 * 1024

    def test_is_production_flag(self):
        from config import settings
        assert isinstance(settings.is_production, bool)

    def test_supported_extensions_complete(self):
        from ingestion.pipeline import SUPPORTED_EXTENSIONS
        required = {".pdf", ".docx", ".pptx", ".csv", ".xlsx", ".txt", ".md"}
        assert required.issubset(SUPPORTED_EXTENSIONS)


# ════════════════════════════════════════════════════════════════════════
# SECTION B — INTEGRATION TESTS (real FastAPI app, SQLite in-memory)
# ════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture(scope="function")
async def app_client():
    """Spin up the full FastAPI app with an isolated SQLite test database."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    TEST_DB = "sqlite+aiosqlite:///./pytest_temp.db"
    test_engine = create_async_engine(TEST_DB, connect_args={"check_same_thread": False})
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)

    from database.models import Base
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from main import app
    from database.connection import get_db

    async def override_db():
        async with TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

    # Cleanup file
    if os.path.exists("./pytest_temp.db"):
        os.remove("./pytest_temp.db")


async def _register_and_login(client, email, password, full_name, role):
    await client.post("/api/v1/auth/register", json={
        "email": email, "password": password,
        "full_name": full_name, "role": role
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": email, "password": password
    })
    return resp.json().get("access_token", "")


class TestAuthIntegration:
    """Req Section 49 — Authentication tests"""

    @pytest.mark.asyncio
    async def test_student_register_success(self, app_client):
        resp = await app_client.post("/api/v1/auth/register", json={
            "email": "student1@test.com", "password": "Test1234!",
            "full_name": "Student One", "role": "STUDENT"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "STUDENT"
        assert data["email"] == "student1@test.com"

    @pytest.mark.asyncio
    async def test_faculty_login_returns_correct_role(self, app_client):
        token = await _register_and_login(app_client, "fac@test.com", "Test1234!", "Faculty One", "FACULTY")
        assert token != ""
        # Verify /me returns correct role
        me = await app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["role"] == "FACULTY"

    @pytest.mark.asyncio
    async def test_admin_login_success(self, app_client):
        token = await _register_and_login(app_client, "adm@test.com", "Test1234!", "Admin One", "ADMIN")
        me = await app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["role"] == "ADMIN"

    @pytest.mark.asyncio
    async def test_wrong_password_rejected(self, app_client):
        await app_client.post("/api/v1/auth/register", json={
            "email": "user@test.com", "password": "Correct1!",
            "full_name": "User", "role": "STUDENT"
        })
        resp = await app_client.post("/api/v1/auth/login", json={
            "email": "user@test.com", "password": "WrongPassword"
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, app_client):
        resp = await app_client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_duplicate_email_rejected(self, app_client):
        payload = {"email": "dup@test.com", "password": "Test1!", "full_name": "Dup", "role": "STUDENT"}
        await app_client.post("/api/v1/auth/register", json=payload)
        resp = await app_client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 400


class TestAuthorizationIntegration:
    """Req Section 49 — Authorization tests"""

    @pytest.mark.asyncio
    async def test_student_denied_admin_endpoint(self, app_client):
        token = await _register_and_login(app_client, "s@t.com", "Test1!", "S", "STUDENT")
        resp = await app_client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_faculty_denied_admin_user_management(self, app_client):
        token = await _register_and_login(app_client, "f@t.com", "Test1!", "F", "FACULTY")
        resp = await app_client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_list_users(self, app_client):
        token = await _register_and_login(app_client, "a@t.com", "Test1!", "A", "ADMIN")
        resp = await app_client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_student_cannot_upload_confidential(self, app_client):
        token = await _register_and_login(app_client, "sc@t.com", "Test1!", "SC", "STUDENT")
        resp = await app_client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"files": ("test.txt", io.BytesIO(b"content"), "text/plain")},
            data={"source_name": "secret", "classification": "CONFIDENTIAL"}
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_student_cannot_set_deadline(self, app_client):
        token = await _register_and_login(app_client, "sd@t.com", "Test1!", "SD", "STUDENT")
        resp = await app_client.post(
            "/api/v1/deadlines/",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "Test", "deadline_date": "2026-12-01", "deadline_time": "14:00:00"}
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_faculty_can_create_deadline(self, app_client):
        token = await _register_and_login(app_client, "fd@t.com", "Test1!", "FD", "FACULTY")
        resp = await app_client.post(
            "/api/v1/deadlines/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "Assignment Deadline",
                "deadline_date": "2026-12-01",
                "deadline_time": "14:00:00",
                "missing_count": 2,
                "missing_names": ["Divya", "Rahul"]
            }
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Assignment Deadline"
        assert data["missing_count"] == 2
        assert "Divya" in data["missing_names"]


class TestDocumentUploadIntegration:
    """Req: Document upload, file validation (Section 40, Phase 2)"""

    @pytest.mark.asyncio
    async def test_student_upload_non_confidential_txt(self, app_client):
        token = await _register_and_login(app_client, "upl@t.com", "Test1!", "Uploader", "STUDENT")
        with patch("ingestion.pipeline.add_documents", AsyncMock(return_value=3)):
            resp = await app_client.post(
                "/api/v1/documents/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"files": ("notes.txt", io.BytesIO(b"Python is great. " * 50), "text/plain")},
                data={"source_name": "My Notes", "classification": "NON_CONFIDENTIAL"}
            )
        assert resp.status_code == 201
        results = resp.json()["results"]
        assert results[0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_invalid_file_type_rejected(self, app_client):
        token = await _register_and_login(app_client, "inv@t.com", "Test1!", "Inv", "STUDENT")
        resp = await app_client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"files": ("virus.exe", io.BytesIO(b"not allowed"), "application/octet-stream")},
            data={"source_name": "Bad"}
        )
        assert resp.status_code == 201  # Returns results, not HTTP error
        results = resp.json()["results"]
        assert results[0]["status"] == "error"
        assert "Unsupported" in results[0]["message"]

    @pytest.mark.asyncio
    async def test_faculty_can_upload_standard_resource(self, app_client):
        token = await _register_and_login(app_client, "fsr@t.com", "Test1!", "FSR", "FACULTY")
        with patch("ingestion.pipeline.add_documents", AsyncMock(return_value=5)):
            resp = await app_client.post(
                "/api/v1/documents/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"files": ("textbook.txt", io.BytesIO(b"Chapter 1. " * 80), "text/plain")},
                data={"source_name": "ML Textbook", "is_standard_resource": "true"}
            )
        assert resp.status_code == 201
        assert resp.json()["results"][0]["status"] == "success"


class TestAnalysisIntegration:
    """Req: Multi-document analysis endpoints (Sections 11, 28, 42)"""

    @pytest.mark.asyncio
    async def test_faculty_missing_responses_endpoint(self, app_client):
        token = await _register_and_login(app_client, "fan@t.com", "Test1!", "FAN", "FACULTY")
        import csv, io as sio

        # Master list
        master_buf = sio.BytesIO()
        writer = csv.writer(sio.TextIOWrapper(master_buf, newline='', write_through=True))
        writer.writerow(["Name"])
        for n in ["Alice", "Bob", "Charlie", "Divya", "Rahul"]:
            writer.writerow([n])
        master_buf.seek(0)

        # Response file (only 3 responded)
        resp_buf = sio.BytesIO()
        writer2 = csv.writer(sio.TextIOWrapper(resp_buf, newline='', write_through=True))
        writer2.writerow(["Name"])
        for n in ["Alice", "Bob", "Charlie"]:
            writer2.writerow([n])
        resp_buf.seek(0)

        resp = await app_client.post(
            "/api/v1/analysis/missing-responses",
            headers={"Authorization": f"Bearer {token}"},
            files={
                "master_file": ("master.csv", master_buf, "text/csv"),
                "response_file": ("responses.csv", resp_buf, "text/csv"),
            },
            data={"master_name_col": "Name", "response_name_col": "Name"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert data["missing_count"] == 2
        assert set(data["missing_names"]) == {"Divya", "Rahul"}

    @pytest.mark.asyncio
    async def test_student_denied_analysis(self, app_client):
        token = await _register_and_login(app_client, "sta@t.com", "Test1!", "STA", "STUDENT")
        resp = await app_client.post(
            "/api/v1/analysis/missing-responses",
            headers={"Authorization": f"Bearer {token}"},
            files={
                "master_file": ("m.csv", io.BytesIO(b"Name\nAlice"), "text/csv"),
                "response_file": ("r.csv", io.BytesIO(b"Name\nAlice"), "text/csv"),
            }
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_responses_yes_no_count(self, app_client):
        token = await _register_and_login(app_client, "ryn@t.com", "Test1!", "RYN", "FACULTY")
        import csv, io as sio

        master_buf = sio.BytesIO()
        w = csv.writer(sio.TextIOWrapper(master_buf, newline='', write_through=True))
        w.writerow(["Name"])
        for n in ["Arun", "Priya", "Karthik", "Divya", "Rahul"]:
            w.writerow([n])
        master_buf.seek(0)

        resp_buf = sio.BytesIO()
        w2 = csv.writer(sio.TextIOWrapper(resp_buf, newline='', write_through=True))
        w2.writerow(["Name", "Response"])
        for row in [("Arun", "Yes"), ("Priya", "No"), ("Karthik", "Yes")]:
            w2.writerow(row)
        resp_buf.seek(0)

        resp = await app_client.post(
            "/api/v1/analysis/responses",
            headers={"Authorization": f"Bearer {token}"},
            files={
                "master_file": ("master.csv", master_buf, "text/csv"),
                "response_file": ("resp.csv", resp_buf, "text/csv"),
            },
            data={"master_name_col": "Name", "response_name_col": "Name", "response_col": "Response"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_students"] == 5
        assert data["yes_count"] == 2
        assert data["no_count"] == 1
        assert data["no_response_count"] == 2


class TestDeadlineIntegration:
    """Req: Deadline creation, scheduler (Sections 28-31)"""

    @pytest.mark.asyncio
    async def test_deadline_stored_correctly(self, app_client):
        token = await _register_and_login(app_client, "dl@t.com", "Test1!", "DL", "FACULTY")
        resp = await app_client.post(
            "/api/v1/deadlines/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "Lab Report Deadline",
                "deadline_date": "2026-11-15",
                "deadline_time": "17:00:00",
                "timezone": "Asia/Kolkata",
                "missing_count": 3,
                "missing_names": ["Student A", "Student B", "Student C"]
            }
        )
        assert resp.status_code == 201
        d = resp.json()
        assert d["title"] == "Lab Report Deadline"
        assert d["deadline_date"] == "2026-11-15"
        assert d["missing_count"] == 3
        assert d["status"] == "ACTIVE"
        assert len(d["missing_names"]) == 3

    @pytest.mark.asyncio
    async def test_list_deadlines(self, app_client):
        token = await _register_and_login(app_client, "ldl@t.com", "Test1!", "LDL", "FACULTY")
        # Create one
        await app_client.post("/api/v1/deadlines/",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "Test DL", "deadline_date": "2026-12-01", "deadline_time": "09:00:00"}
        )
        resp = await app_client.get("/api/v1/deadlines/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_notifications_endpoint_accessible(self, app_client):
        token = await _register_and_login(app_client, "nf@t.com", "Test1!", "NF", "FACULTY")
        resp = await app_client.get("/api/v1/deadlines/notifications",
                                    headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestAPIUsageDashboard:
    """Req: Admin usage dashboard (Sections 18, 44)"""

    @pytest.mark.asyncio
    async def test_admin_can_access_usage_summary(self, app_client):
        token = await _register_and_login(app_client, "aus@t.com", "Test1!", "AUS", "ADMIN")
        with patch("models.router.model_router.check_local_availability", AsyncMock(return_value=True)):
            resp = await app_client.get("/api/v1/admin/api-usage/summary",
                                        headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        # Must have usage info but NO API keys
        assert "today" in data
        assert "month" in data
        assert "api_key" not in str(data).lower()
        assert "sk-" not in str(data)

    @pytest.mark.asyncio
    async def test_student_denied_usage_dashboard(self, app_client):
        token = await _register_and_login(app_client, "sud@t.com", "Test1!", "SUD", "STUDENT")
        resp = await app_client.get("/api/v1/admin/api-usage/summary",
                                    headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_audit_logs_accessible_to_admin(self, app_client):
        token = await _register_and_login(app_client, "aud@t.com", "Test1!", "AUD", "ADMIN")
        resp = await app_client.get("/api/v1/admin/audit-logs",
                                    headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestHealthEndpoint:
    """Basic sanity — app is running"""

    @pytest.mark.asyncio
    async def test_health_check(self, app_client):
        resp = await app_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_docs_accessible(self, app_client):
        resp = await app_client.get("/api/docs")
        assert resp.status_code == 200
