# Secure & Intelligent Agentic RAG Platform

> A production-grade, full-stack Agentic RAG platform for college/educational environments. Built with security, modularity, and intelligence at its core.

## 🏗️ Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the complete architecture design.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or SQLite for dev)
- Redis (optional, for caching)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
# Edit .env with your credentials
alembic upgrade head
uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local
npm run dev
```

## 📋 Implementation Phases

| Phase | Feature | Branch |
|-------|---------|--------|
| 1 | Basic RAG Pipeline | `phase/1-basic-rag` |
| 2 | Multi-format Ingestion | `phase/2-multiformat` |
| 3 | Standard Resources | `phase/3-standard-resources` |
| 4 | LangGraph Agent | `phase/4-langgraph` |
| 5 | Auth & RBAC | `phase/5-auth-rbac` |
| 6 | Structured Data + GSheets | `phase/6-structured-data` |
| 7 | External Web Search | `phase/7-web-search` |
| 8 | Multi-Document Analysis | `phase/8-multi-doc` |
| 9 | Deadline + Scheduler | `phase/9-deadlines` |
| 10 | API Usage Monitoring | `phase/10-usage-monitoring` |
| 11 | Local LLM Fallback | `phase/11-local-llm` |
| 12 | Production Hardening | `phase/12-production` |

## 🔐 Security

- JWT authentication with httpOnly cookies
- Multi-layer RBAC (role → source → department → user)
- Retrieval-time metadata filtering (confidential data never reaches LLM unauthorized)
- Audit logging for all access events
- No hardcoded API keys — all via environment variables / secret manager

## 📁 Project Structure

```
rag-platform/
├── frontend/         # Next.js application
├── backend/          # FastAPI application
├── tests/            # Test suite
├── local_models/     # Local LLM configuration
├── migrations/       # Alembic DB migrations
├── docs/             # Documentation
├── docker-compose.yml
└── .env.example
```

## 🧪 Testing

```bash
cd tests
pytest -v
```

## 🐳 Docker

```bash
docker-compose up -d
```

## 📄 License

Educational use. See LICENSE.
