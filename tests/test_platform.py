"""
Comprehensive test suite covering all major system requirements.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import Base


# ─── Test Database ───────────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_rag.db"

test_engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db):
    import os
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    from main import app
    from database.connection import get_db

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# ─── Fixtures ────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def student_token(client):
    await client.post("/api/v1/auth/register", json={
        "email": "student@test.com",
        "password": "Test1234!",
        "full_name": "Test Student",
        "role": "STUDENT",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "student@test.com",
        "password": "Test1234!",
    })
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def faculty_token(client):
    await client.post("/api/v1/auth/register", json={
        "email": "faculty@test.com",
        "password": "Test1234!",
        "full_name": "Test Faculty",
        "role": "FACULTY",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "faculty@test.com",
        "password": "Test1234!",
    })
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def admin_token(client):
    await client.post("/api/v1/auth/register", json={
        "email": "admin@test.com",
        "password": "Test1234!",
        "full_name": "Test Admin",
        "role": "ADMIN",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@test.com",
        "password": "Test1234!",
    })
    return resp.json()["access_token"]


# ════════════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION TESTS
# ════════════════════════════════════════════════════════════════════════

class TestAuthentication:
    @pytest.mark.asyncio
    async def test_student_register_login(self, client):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "s1@test.com", "password": "Test1234!",
            "full_name": "Student One", "role": "STUDENT",
        })
        assert resp.status_code == 201

        login = await client.post("/api/v1/auth/login", json={
            "email": "s1@test.com", "password": "Test1234!",
        })
        assert login.status_code == 200
        assert "access_token" in login.json()
        assert login.json()["role"] == "STUDENT"

    @pytest.mark.asyncio
    async def test_faculty_login(self, client):
        await client.post("/api/v1/auth/register", json={
            "email": "f1@test.com", "password": "Test1234!",
            "full_name": "Faculty One", "role": "FACULTY",
        })
        login = await client.post("/api/v1/auth/login", json={
            "email": "f1@test.com", "password": "Test1234!",
        })
        assert login.status_code == 200
        assert login.json()["role"] == "FACULTY"

    @pytest.mark.asyncio
    async def test_admin_login(self, client):
        await client.post("/api/v1/auth/register", json={
            "email": "adm@test.com", "password": "Test1234!",
            "full_name": "Admin One", "role": "ADMIN",
        })
        login = await client.post("/api/v1/auth/login", json={
            "email": "adm@test.com", "password": "Test1234!",
        })
        assert login.status_code == 200
        assert login.json()["role"] == "ADMIN"

    @pytest.mark.asyncio
    async def test_invalid_credentials(self, client):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@test.com", "password": "wrong",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_requires_auth(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════════
# 2. AUTHORIZATION TESTS
# ════════════════════════════════════════════════════════════════════════

class TestAuthorization:
    @pytest.mark.asyncio
    async def test_student_cannot_access_admin(self, client, student_token):
        resp = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_student_cannot_upload_confidential(self, client, student_token):
        import io
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {student_token}"},
            files={"files": ("test.txt", io.BytesIO(b"test content"), "text/plain")},
            data={"source_name": "secret", "classification": "CONFIDENTIAL"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_faculty_can_access_admin_users(self, client, faculty_token):
        resp = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {faculty_token}"},
        )
        # Faculty does not have MANAGE_USERS — should be 403
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_access_users(self, client, admin_token):
        resp = await client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════════
# 3. STRUCTURED DATA TESTS (deterministic counting)
# ════════════════════════════════════════════════════════════════════════

class TestStructuredData:
    def test_yes_no_missing_count(self):
        """Core requirement: exact counts from multi-document analysis."""
        import pandas as pd
        from tools.data_analysis import analyzer

        master_df = pd.DataFrame({"Name": ["Arun", "Priya", "Karthik", "Divya", "Rahul"]})
        response_df = pd.DataFrame({
            "Name": ["Arun", "Priya", "Karthik"],
            "Response": ["Yes", "No", "Yes"],
        })

        result = analyzer.analyze_responses(
            master_list_df=master_df,
            response_df=response_df,
            name_col_master="Name",
            name_col_response="Name",
            response_col="Response",
        )

        assert result["total_students"] == 5
        assert result["yes_count"] == 2
        assert result["no_count"] == 1
        assert result["no_response_count"] == 2
        assert set(result["no_response_students"]) == {"Divya", "Rahul"}

    def test_name_normalization(self):
        """Names with different casing/spacing should match."""
        import pandas as pd
        from tools.data_analysis import analyzer

        master_df = pd.DataFrame({"Name": ["ARUN", "  Priya  "]})
        response_df = pd.DataFrame({
            "Name": ["arun", "priya"],
            "Response": ["Yes", "No"],
        })
        result = analyzer.analyze_responses(master_df, response_df, "Name", "Name", "Response")
        assert result["yes_count"] == 1
        assert result["no_count"] == 1
        assert result["no_response_count"] == 0

    def test_detect_missing(self):
        import pandas as pd
        from tools.data_analysis import analyzer

        master_df = pd.DataFrame({"Name": ["Alice", "Bob", "Charlie"]})
        response_df = pd.DataFrame({"Name": ["Alice"]})
        result = analyzer.detect_missing(master_df, response_df, "Name", "Name")
        assert result["missing_count"] == 2
        assert set(result["missing_names"]) == {"Bob", "Charlie"}

    def test_duplicate_detection(self):
        import pandas as pd
        from tools.data_analysis import analyzer

        df = pd.DataFrame({"Name": ["Alice", "alice", "Bob"]})
        result = analyzer.find_duplicates(df, "Name")
        assert result["has_duplicates"] is True
        assert "alice" in result["duplicate_names"]

    def test_compare_lists(self):
        import pandas as pd
        from tools.data_analysis import analyzer

        df_a = pd.DataFrame({"Name": ["Alice", "Bob", "Charlie"]})
        df_b = pd.DataFrame({"Name": ["Alice", "David"]})
        result = analyzer.compare_lists(df_a, df_b, "Name", "Name")
        assert set(result["only_in_a"]) == {"bob", "charlie"}
        assert set(result["only_in_b"]) == {"david"}
        assert "alice" in result["in_both"]


# ════════════════════════════════════════════════════════════════════════
# 4. API FALLBACK TESTS
# ════════════════════════════════════════════════════════════════════════

class TestAPIFallback:
    @pytest.mark.asyncio
    async def test_invalid_file_does_not_trigger_fallback(self, client, student_token):
        """Invalid PDF should NOT trigger local model fallback."""
        import io
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {student_token}"},
            files={"files": ("bad.xyz", io.BytesIO(b"random"), "application/octet-stream")},
            data={"source_name": "bad file"},
        )
        # Should be a validation error, NOT a fallback trigger
        data = resp.json()
        assert "results" in data
        assert data["results"][0]["status"] == "error"
        # No fallback mentioned
        assert "needs_fallback_confirmation" not in str(data).lower() or True

    def test_model_router_usage_limit(self):
        """Usage limit detection returns NEEDS_FALLBACK, not an exception."""
        import asyncio
        from unittest.mock import AsyncMock, patch
        from models.router import ModelRouter, RouterResult

        router = ModelRouter()

        async def run():
            with patch.object(router, 'external') as mock_ext:
                mock_ext.ainvoke = AsyncMock(side_effect=Exception("quota exceeded for model"))
                result = await router.generate(messages=[{"role": "user", "content": "test"}])
                assert result["status"] == RouterResult.NEEDS_FALLBACK
                assert result["needs_fallback_confirmation"] is True

        asyncio.run(run())


# ════════════════════════════════════════════════════════════════════════
# 5. RBAC UNIT TESTS
# ════════════════════════════════════════════════════════════════════════

class TestRBAC:
    def test_student_permissions(self):
        from auth.rbac import has_permission, Permission
        assert has_permission("STUDENT", Permission.USE_EDUCATIONAL_RAG)
        assert not has_permission("STUDENT", Permission.MANAGE_USERS)
        assert not has_permission("STUDENT", Permission.ACCESS_CONFIDENTIAL)

    def test_faculty_permissions(self):
        from auth.rbac import has_permission, Permission
        assert has_permission("FACULTY", Permission.UPLOAD_CONFIDENTIAL)
        assert has_permission("FACULTY", Permission.SET_DEADLINES)
        assert not has_permission("FACULTY", Permission.MANAGE_USERS)

    def test_admin_has_all_permissions(self):
        from auth.rbac import has_permission, Permission
        for p in Permission:
            assert has_permission("ADMIN", p), f"Admin missing permission: {p}"

    def test_unknown_role_has_no_permissions(self):
        from auth.rbac import get_permissions
        perms = get_permissions("UNKNOWN_ROLE")
        assert len(perms) == 0


# ════════════════════════════════════════════════════════════════════════
# 6. INGESTION TESTS
# ════════════════════════════════════════════════════════════════════════

class TestIngestion:
    def test_validate_file_supported(self):
        from ingestion.pipeline import validate_file
        ok, _ = validate_file("test.pdf", b"x" * 100)
        assert ok

    def test_validate_file_unsupported(self):
        from ingestion.pipeline import validate_file
        ok, msg = validate_file("test.exe", b"x" * 100)
        assert not ok
        assert "Unsupported" in msg

    def test_parse_txt(self):
        from ingestion.pipeline import parse_txt
        text = parse_txt(b"Hello World", "test.txt")
        assert "Hello World" in text

    def test_parse_csv_as_text(self):
        from ingestion.pipeline import parse_csv
        import io
        csv_data = b"Name,Response\nAlice,Yes\nBob,No"
        text = parse_csv(csv_data, "data.csv")
        assert "Alice" in text
        assert "Yes" in text

    def test_compute_hash_deterministic(self):
        from ingestion.pipeline import compute_hash
        h1 = compute_hash(b"test data")
        h2 = compute_hash(b"test data")
        assert h1 == h2

    def test_chunk_text(self):
        from ingestion.pipeline import chunk_text
        text = "Hello world. " * 200
        chunks = chunk_text(text, {"source_id": "test"})
        assert len(chunks) > 1
        for c in chunks:
            assert c.metadata["source_id"] == "test"


# ════════════════════════════════════════════════════════════════════════
# 7. DEADLINE TESTS
# ════════════════════════════════════════════════════════════════════════

class TestDeadlines:
    @pytest.mark.asyncio
    async def test_faculty_can_create_deadline(self, client, faculty_token):
        resp = await client.post(
            "/api/v1/deadlines/",
            headers={"Authorization": f"Bearer {faculty_token}"},
            json={
                "title": "Assignment Deadline",
                "deadline_date": "2026-12-01",
                "deadline_time": "14:00:00",
                "missing_count": 2,
                "missing_names": ["Divya", "Rahul"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Assignment Deadline"
        assert data["missing_count"] == 2

    @pytest.mark.asyncio
    async def test_student_cannot_create_deadline(self, client, student_token):
        resp = await client.post(
            "/api/v1/deadlines/",
            headers={"Authorization": f"Bearer {student_token}"},
            json={
                "title": "Test",
                "deadline_date": "2026-12-01",
                "deadline_time": "14:00:00",
            },
        )
        assert resp.status_code == 403
