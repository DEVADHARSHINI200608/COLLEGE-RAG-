# Secure & Intelligent Agentic RAG Platform — Architecture

## Overview
A production-grade, full-stack Agentic RAG platform for a college/educational environment.
This system is **not** a simple chatbot. It is a secure, source-aware, multi-modal AI agent.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (Next.js)                         │
│  Dashboard | Documents | Ask AI | Multi-Doc | Deadlines | Settings  │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ HTTPS/REST/WebSocket
┌─────────────────────────────────▼───────────────────────────────────┐
│                         BACKEND (FastAPI)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │   Auth   │ │   RBAC   │ │Ingestion │ │  Agent   │ │Scheduler │ │
│  │  (JWT)   │ │          │ │ Pipeline │ │ (Graph)  │ │  (APSch) │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
          ┌───────────────────────┼────────────────────┐
          │                       │                    │
┌─────────▼──────┐    ┌──────────▼────────┐  ┌───────▼──────┐
│  Vector DB     │    │  Structured DB    │  │ File Storage │
│  (ChromaDB /   │    │  (PostgreSQL /    │  │  (Local /    │
│   Weaviate)    │    │   SQLite)         │  │   S3)        │
└────────────────┘    └───────────────────┘  └──────────────┘
          │                       │
          └──────────┬────────────┘
                     │
          ┌──────────▼────────────┐
          │    LangGraph Agent    │
          │  ┌─────────────────┐  │
          │  │  Model Router   │  │
          │  │  ┌───────────┐  │  │
          │  │  │ Ext. LLM  │  │  │
          │  │  │ Local LLM │  │  │
          │  │  └───────────┘  │  │
          │  └─────────────────┘  │
          └───────────────────────┘
```

---

## 2. Information Domains

| Domain | Classification | Access |
|--------|---------------|--------|
| Confidential / Institutional | CONFIDENTIAL | Faculty, Admin (role + source level) |
| Educational / Non-Confidential | NON_CONFIDENTIAL | Students, Faculty, Admin |

---

## 3. User Roles & Permissions

| Permission | Student | Faculty | Admin |
|------------|---------|---------|-------|
| Upload own learning materials | ✅ | ✅ | ✅ |
| Access Standard Resources | ✅ | ✅ | ✅ |
| Use educational RAG | ✅ | ✅ | ✅ |
| Use external web search | ✅ (configurable) | ✅ | ✅ |
| Upload/manage Standard Resources | ❌ | ✅ | ✅ |
| Access confidential sources | ❌ | ✅ (authorized) | ✅ |
| Analyze student responses | ❌ | ✅ | ✅ |
| Set deadlines | ❌ | ✅ | ✅ |
| Manage users/roles | ❌ | ❌ | ✅ |
| Monitor API usage | ❌ | ❌ | ✅ |
| Configure system | ❌ | ❌ | ✅ |

---

## 4. LangGraph Agent Graph

```
START
  ↓
[load_user_context]       — Load JWT claims, user role, permissions
  ↓
[authenticate_authorize]  — Validate token, check active session
  ↓
[classify_intent]         — NL classification: educational / confidential / structured / multi-doc
  ↓
[classify_security]       — Determine required classification level
  ↓
[select_sources]          — Filter authorized sources by role + metadata
  ↓
[retrieve]                — Hybrid: vector + structured + web
  │
  ├── [vector_search]     — For documents, PDFs, PPTs, notes
  ├── [structured_query]  — For CSVs, sheets, DB records
  └── [web_search]        — Only if insufficient + permitted
  ↓
[structured_analysis]     — Multi-doc comparison, counting, matching (deterministic)
  ↓
[model_router]            — Check external LLM availability → route
  │
  ├── [external_llm]      — Primary generation
  └── [local_llm]         — Fallback (user-confirmed)
  ↓
[validate_response]       — Sanitize, check for leakage
  ↓
END
```

### Deadline Workflow Graph
```
[detect_missing_responses]
  ↓
[count_missing]
  ↓
[faculty_review]
  ↓
[set_deadline]
  ↓
[scheduler_trigger]
  ↓
[send_notification]
```

---

## 5. Hybrid Retrieval Architecture

```
                    LANGGRAPH AGENT
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    Vector Search   Structured Query  Web Search
    (Semantic)      (Deterministic)   (Public only)
          │               │               │
    ChromaDB/        PostgreSQL/      DuckDuckGo/
    Weaviate         SQLite/GSheets   Tavily/SerpAPI
```

### Source Priority for Student Educational Queries:
1. Student's own uploaded materials
2. Standard Resources (faculty-approved)
3. External web search (only if insufficient + permitted)

---

## 6. Security Architecture

### Authentication
- JWT-based auth (access + refresh tokens)
- Token stored in httpOnly cookies
- CSRF protection

### Authorization (Multi-layer)
```
Request
  ↓ Layer 1: JWT validation
  ↓ Layer 2: Role check (RBAC)
  ↓ Layer 3: Source-level permission check
  ↓ Layer 4: Department-level filter (if applicable)
  ↓ Layer 5: Retrieval-time metadata filter
  ↓ Authorized Data Only → LLM
```

### Vector Metadata Security
Every confidential chunk stored with:
```json
{
  "classification": "CONFIDENTIAL",
  "allowed_roles": ["FACULTY", "ADMIN"],
  "allowed_departments": ["IT", "CSE"],
  "source_id": "src_xyz",
  "owner_id": "user_123"
}
```
Metadata filter applied BEFORE semantic search — not after.

---

## 7. Model Router Architecture

```
ModelRouter
  ├── check_availability()  → APIUsageMonitor
  ├── use_external()        → ExternalLLMClient (OpenAI/Gemini/Anthropic)
  ├── request_fallback()    → FallbackManager → User Confirmation
  └── use_local()           → LocalLLMClient (Ollama/LlamaCPP)
```

### Fallback States
| State | Action |
|-------|--------|
| EXTERNAL_AVAILABLE | Use external LLM |
| RATE_LIMITED | Retry with backoff, then fallback prompt |
| QUOTA_EXCEEDED | Immediate fallback prompt |
| BUDGET_EXCEEDED | Immediate fallback prompt |
| API_UNAVAILABLE | Immediate fallback prompt |
| API_TIMEOUT | Retry N times, then fallback prompt |
| USER_CONFIRMED_LOCAL | Use local LLM |
| USER_REJECTED_LOCAL | Return polite error |

---

## 8. Database Schemas

### Users Table
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  hashed_password TEXT NOT NULL,
  full_name VARCHAR(255),
  role VARCHAR(50) NOT NULL DEFAULT 'STUDENT',
  department VARCHAR(100),
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Sources Table
```sql
CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_name VARCHAR(500) NOT NULL,
  source_type VARCHAR(50) NOT NULL,  -- PDF, CSV, XLSX, URL, GSHEETS, DB
  classification VARCHAR(20) NOT NULL,  -- CONFIDENTIAL, NON_CONFIDENTIAL
  is_standard_resource BOOLEAN DEFAULT false,
  is_student_uploaded BOOLEAN DEFAULT false,
  is_external BOOLEAN DEFAULT false,
  owner_id UUID REFERENCES users(id),
  uploaded_by UUID REFERENCES users(id),
  department VARCHAR(100),
  access_roles TEXT[],  -- ['FACULTY', 'ADMIN']
  allowed_users UUID[],
  allowed_departments TEXT[],
  file_path TEXT,
  external_url TEXT,
  version INTEGER DEFAULT 1,
  status VARCHAR(20) DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Deadlines Table
```sql
CREATE TABLE deadlines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(500) NOT NULL,
  deadline_date DATE NOT NULL,
  deadline_time TIME NOT NULL,
  timezone VARCHAR(100) DEFAULT 'Asia/Kolkata',
  created_by UUID REFERENCES users(id),
  target_group VARCHAR(100),
  target_source_id UUID REFERENCES sources(id),
  status VARCHAR(20) DEFAULT 'ACTIVE',
  missing_count INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Notifications Table
```sql
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  deadline_id UUID REFERENCES deadlines(id),
  recipient_id UUID REFERENCES users(id),
  message TEXT NOT NULL,
  is_read BOOLEAN DEFAULT false,
  sent_at TIMESTAMPTZ DEFAULT NOW()
);
```

### API Usage Table
```sql
CREATE TABLE api_usage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  provider VARCHAR(100),
  model VARCHAR(100),
  request_tokens INTEGER DEFAULT 0,
  response_tokens INTEGER DEFAULT 0,
  total_tokens INTEGER DEFAULT 0,
  estimated_cost_usd NUMERIC(10,6),
  status VARCHAR(50),  -- SUCCESS, RATE_LIMITED, QUOTA_EXCEEDED, etc.
  was_fallback BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Audit Logs Table
```sql
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  action VARCHAR(200) NOT NULL,
  resource_type VARCHAR(100),
  resource_id UUID,
  ip_address INET,
  user_agent TEXT,
  details JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 9. API Contracts

### Auth
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET  /api/v1/auth/me`

### Documents / Sources
- `POST /api/v1/documents/upload`
- `GET  /api/v1/documents/`
- `GET  /api/v1/documents/{id}`
- `DELETE /api/v1/documents/{id}`
- `POST /api/v1/documents/url`

### Standard Resources
- `GET  /api/v1/resources/standard`
- `POST /api/v1/resources/standard` (faculty/admin)
- `DELETE /api/v1/resources/standard/{id}`

### Ask AI / Chat
- `POST /api/v1/chat/query`
- `GET  /api/v1/chat/history`
- `POST /api/v1/chat/confirm-local-model`

### Multi-Document Analysis
- `POST /api/v1/analysis/multi-doc`
- `POST /api/v1/analysis/missing-responses`

### Google Sheets
- `POST /api/v1/integrations/gsheets/connect`
- `GET  /api/v1/integrations/gsheets/{id}/data`

### Deadlines
- `POST /api/v1/deadlines/`
- `GET  /api/v1/deadlines/`
- `GET  /api/v1/deadlines/{id}`
- `PUT  /api/v1/deadlines/{id}`

### Notifications
- `GET  /api/v1/notifications/`
- `PUT  /api/v1/notifications/{id}/read`

### API Usage (Admin)
- `GET  /api/v1/admin/api-usage`
- `GET  /api/v1/admin/api-usage/summary`

### Admin
- `GET  /api/v1/admin/users`
- `POST /api/v1/admin/users`
- `PUT  /api/v1/admin/users/{id}/role`
- `GET  /api/v1/admin/settings`
- `PUT  /api/v1/admin/settings`

---

## 10. Environment Variables

See `.env.example` in project root.

---

## 11. Agent Tools Registry

| Tool | Description | Access |
|------|-------------|--------|
| `document_retriever` | Retrieve by source_id | Filtered by auth |
| `vector_search` | Semantic search with metadata filter | Auth-filtered |
| `structured_data_query` | Deterministic query on CSV/sheets/DB | Auth-filtered |
| `google_sheets_tool` | Live Google Sheets API fetch | Backend-controlled |
| `database_tool` | Parameterized DB query | Backend-controlled |
| `url_fetcher` | Fetch approved URLs | Non-confidential only |
| `web_search_tool` | External public web search | Non-confidential, permitted |
| `document_comparison_tool` | Multi-doc analysis | Auth-filtered |
| `data_analysis_tool` | Counting, matching, deduplication | Deterministic |
| `deadline_tool` | Create/read deadlines | Faculty/Admin |
| `scheduler_tool` | Trigger scheduled checks | Backend only |
| `notification_tool` | Send notifications | Backend only |
| `usage_monitor_tool` | Check API availability/usage | Backend only |
| `external_llm_tool` | Call external LLM | Via ModelRouter |
| `local_llm_tool` | Call local LLM | Via ModelRouter |

---

## 12. Project Folder Structure

```
rag-platform/
├── frontend/                    # Next.js app
│   ├── src/
│   │   ├── app/                 # App router pages
│   │   ├── components/          # Reusable components
│   │   ├── hooks/               # Custom hooks
│   │   ├── lib/                 # API clients
│   │   └── types/               # TypeScript types
│   └── package.json
│
├── backend/                     # FastAPI app
│   ├── api/                     # Route handlers
│   │   ├── v1/
│   │   │   ├── auth.py
│   │   │   ├── documents.py
│   │   │   ├── chat.py
│   │   │   ├── analysis.py
│   │   │   ├── deadlines.py
│   │   │   ├── notifications.py
│   │   │   ├── admin.py
│   │   │   └── integrations.py
│   ├── auth/                    # JWT, RBAC
│   │   ├── jwt_handler.py
│   │   ├── rbac.py
│   │   └── dependencies.py
│   ├── agents/                  # LangGraph agent
│   │   ├── graph.py             # Main agent graph
│   │   ├── nodes/               # Each graph node
│   │   │   ├── load_context.py
│   │   │   ├── classify_intent.py
│   │   │   ├── classify_security.py
│   │   │   ├── select_sources.py
│   │   │   ├── retrieve.py
│   │   │   ├── structured_analysis.py
│   │   │   ├── web_search.py
│   │   │   └── validate_response.py
│   │   └── state.py             # AgentState TypedDict
│   ├── tools/                   # Agent tools
│   │   ├── vector_search.py
│   │   ├── structured_query.py
│   │   ├── google_sheets.py
│   │   ├── database_tool.py
│   │   ├── url_fetcher.py
│   │   ├── web_search.py
│   │   ├── document_comparison.py
│   │   ├── data_analysis.py
│   │   ├── deadline_tool.py
│   │   ├── notification_tool.py
│   │   └── usage_monitor.py
│   ├── models/                  # LLM abstraction
│   │   ├── router.py            # ModelRouter
│   │   ├── external_llm.py      # OpenAI/Gemini/Anthropic
│   │   ├── local_llm.py         # Ollama/LlamaCPP
│   │   ├── embeddings.py        # Embedding model
│   │   └── fallback.py          # FallbackManager
│   ├── retrieval/               # Hybrid retrieval
│   │   ├── vector_store.py      # ChromaDB/Weaviate client
│   │   ├── retriever.py         # Orchestrates retrieval
│   │   └── filters.py           # Auth-aware metadata filters
│   ├── ingestion/               # Document parsing
│   │   ├── pipeline.py          # Main pipeline
│   │   ├── parsers/
│   │   │   ├── pdf_parser.py
│   │   │   ├── docx_parser.py
│   │   │   ├── pptx_parser.py
│   │   │   ├── csv_parser.py
│   │   │   ├── xlsx_parser.py
│   │   │   └── txt_parser.py
│   │   └── chunker.py
│   ├── database/                # DB models & connections
│   │   ├── connection.py
│   │   ├── models.py            # SQLAlchemy models
│   │   └── crud/
│   ├── security/                # Security utilities
│   │   ├── encryption.py
│   │   ├── audit.py
│   │   └── validators.py
│   ├── scheduler/               # APScheduler
│   │   ├── scheduler.py
│   │   └── jobs.py
│   ├── notifications/
│   │   └── service.py
│   ├── monitoring/              # API usage monitoring
│   │   ├── usage_tracker.py
│   │   └── availability.py
│   ├── services/                # Business logic
│   │   ├── analysis_service.py
│   │   └── deadline_service.py
│   ├── config.py                # Settings (pydantic-settings)
│   └── main.py                  # FastAPI app entry
│
├── tests/
│   ├── test_auth.py
│   ├── test_authorization.py
│   ├── test_rag.py
│   ├── test_structured_data.py
│   ├── test_web_search.py
│   ├── test_api_fallback.py
│   └── test_deadlines.py
│
├── local_models/                # Local LLM config
│   └── README.md
│
├── migrations/                  # Alembic migrations
│
├── docs/
│   ├── ARCHITECTURE.md          # This file
│   ├── API.md
│   └── DEPLOYMENT.md
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 13. Implementation Phases

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Basic RAG pipeline (upload → parse → embed → retrieve → answer) | 🔨 |
| 2 | Multi-format ingestion (PDF, DOCX, PPTX, CSV, XLSX, TXT) | ⏳ |
| 3 | Standard Resources system | ⏳ |
| 4 | LangGraph agent orchestration | ⏳ |
| 5 | Authentication & confidential access control | ⏳ |
| 6 | Structured data processing + Google Sheets | ⏳ |
| 7 | External web search | ⏳ |
| 8 | Multi-document comparison | ⏳ |
| 9 | Missing response + deadline + scheduler | ⏳ |
| 10 | External API usage monitoring | ⏳ |
| 11 | Local LLM fallback | ⏳ |
| 12 | Production hardening, testing, deployment | ⏳ |
