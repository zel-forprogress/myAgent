# myAgent

myAgent is a local RAG Agent demo built around FastAPI, LangGraph, Milvus, PostgreSQL, MinIO, Next.js, and Langfuse. It supports document ingestion, multi-knowledge-base retrieval, chat session persistence, streaming chat responses, and an admin console for knowledge-base management.

## Features

- RAG chat with Qwen-compatible OpenAI API calls
- LangGraph-based Agent workflow
- Streaming answer output
- Multi-knowledge-base selection
- Document upload and parsing for `.txt`, `.md`, `.pdf`, and `.docx`
- Vector retrieval with Milvus
- Chat sessions and user data persisted in PostgreSQL
- Original files stored in MinIO object storage
- Langfuse tracing for Agent steps, retrieval, and model calls
- Next.js frontend with chat page, login page, and admin console
- Basic user roles: admin and normal user

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python, FastAPI, Uvicorn |
| Agent workflow | LangGraph |
| RAG components | LangChain |
| LLM API | OpenAI-compatible API, DashScope/Qwen |
| Vector database | Milvus |
| Relational database | PostgreSQL |
| Object storage | MinIO |
| Observability | Langfuse |
| Frontend | Next.js, React, TypeScript |
| Deployment dependencies | Docker Compose |

## Project Structure

```text
myAgent/
+-- rag-backend/
|   +-- app/
|   |   +-- api/              # FastAPI route layer
|   |   +-- core/             # config and database initialization
|   |   +-- models/           # SQLAlchemy models
|   |   +-- schemas/          # request/response schemas
|   |   +-- services/         # RAG, graph, storage, auth, chat logic
|   +-- data/docs/            # local development documents
|   +-- docs/                 # backend notes
|   +-- docker-compose.yml    # PostgreSQL, Milvus, MinIO, etcd
|   +-- requirements.txt
+-- rag-frontend/
|   +-- app/                  # Next.js pages
|   +-- components/           # shared UI components
|   +-- lib/                  # frontend API/auth helpers
|   +-- package.json
+-- docs/
    +-- STARTUP.md            # detailed startup guide
```

## Quick Start

Read [docs/STARTUP.md](docs/STARTUP.md) for the full startup and test flow.

Short version:

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
copy .env.example .env
docker compose up -d
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then start the frontend:

```powershell
cd D:\code\git_localRepository\myAgent\rag-frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Open:

- Frontend: http://localhost:3000
- Backend Swagger: http://127.0.0.1:8000/docs
- MinIO Console: http://127.0.0.1:9001

## Default Accounts

The backend seeds two local accounts on startup:

| Role | Username | Password |
| --- | --- | --- |
| Admin | `admin` | `admin123456` |
| User | `demo` | `demo123456` |

Change these values in `rag-backend/.env` before using this outside local development.

## Common Development Commands

Backend:

```powershell
cd rag-backend
docker compose up -d
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd rag-frontend
npm run dev
```

Stop Docker services:

```powershell
cd rag-backend
docker compose down
```

## Notes

- Do not commit `.env` or `.env.local`; use the example files as templates.
- Uploaded files are stored in MinIO. Parsed chunks are stored in Milvus.
- Chat sessions and metadata are stored in PostgreSQL.
- If port `3000` is occupied, Next.js may automatically switch to another port such as `3001`.
