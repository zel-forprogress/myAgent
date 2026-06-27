# Startup Guide

This guide explains how to run myAgent locally from a clean checkout.

## 1. Prerequisites

Install these tools first:

- Docker Desktop
- Python 3.11 or newer
- Conda or another Python virtual environment tool
- Node.js 20 or newer
- npm

Recommended local services are started by Docker Compose:

- PostgreSQL
- etcd
- MinIO
- Milvus

## 2. Backend Environment

Create the backend environment file:

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
copy .env.example .env
```

Edit `rag-backend/.env` and fill in your real DashScope/Qwen API key:

```env
OPENAI_API_KEY=your_dashscope_api_key
```

The project uses DashScope through the OpenAI-compatible endpoint:

```env
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
CHAT_MODEL=qwen3.7-plus
EMBEDDING_MODEL=text-embedding-v4
```

If you use a different Qwen chat model, change `CHAT_MODEL`.

## 3. Start Docker Services

Start PostgreSQL, Milvus, MinIO, and etcd:

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
docker compose up -d
```

Check containers:

```powershell
docker compose ps
```

Useful service URLs:

- Milvus: `localhost:19530`
- PostgreSQL: `localhost:5433`
- MinIO API: `http://127.0.0.1:9000`
- MinIO Console: `http://127.0.0.1:9001`

MinIO local account:

```text
username: minioadmin
password: minioadmin
```

## 4. Install Backend Dependencies

Create and activate a Python environment:

```powershell
conda create -n rag-agent python=3.11 -y
conda activate rag-agent
```

Install dependencies:

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
pip install -r requirements.txt
```

## 5. Start Backend

Run FastAPI:

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
uvicorn app.main:app --reload
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
GET http://127.0.0.1:8000/health
```

Expected result:

```json
{
  "status": "ok"
}
```

## 6. Frontend Environment

Create the frontend environment file:

```powershell
cd D:\code\git_localRepository\myAgent\rag-frontend
copy .env.local.example .env.local
```

Default frontend API address:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## 7. Install and Start Frontend

Install frontend dependencies:

```powershell
cd D:\code\git_localRepository\myAgent\rag-frontend
npm install
```

Start Next.js:

```powershell
npm run dev
```

Open:

```text
http://localhost:3000
```

If port `3000` is already occupied, Next.js may start on `3001`. Use the URL printed in the terminal.

## 8. Login

Default accounts:

| Role | Username | Password |
| --- | --- | --- |
| Admin | `admin` | `admin123456` |
| User | `demo` | `demo123456` |

Admin users can open the admin console. Normal users can only use the chat page.

## 9. Basic Test Flow

1. Open `http://localhost:3000`.
2. Login as `admin`.
3. Enter the admin console.
4. Create a knowledge base.
5. Open that knowledge base.
6. Upload a `.txt`, `.md`, `.pdf`, or `.docx` file.
7. Confirm the file appears in MinIO.
8. Confirm document chunks appear in the admin document list.
9. Return to chat.
10. Ask a question related to the uploaded document.
11. Check that the answer includes retrieval sources.

## 10. Langfuse

Langfuse is optional. If these values are empty, the core RAG flow still works.

```env
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TIMEOUT=30
```

After filling these values, restart the backend and run a chat request. Open the Langfuse tracing page to confirm spans and generations are recorded.

## 11. Troubleshooting

### Docker pull failed

If Docker reports `failed to fetch oauth token` or `EOF`, it is usually a network issue. Retry:

```powershell
docker compose up -d
```

### Docker daemon is not running

Start Docker Desktop first, then run:

```powershell
docker compose up -d
```

### Backend cannot import `app`

Run Uvicorn from `rag-backend`, not the repository root:

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
uvicorn app.main:app --reload
```

### Frontend reports connection error

Confirm the backend is running:

```text
http://127.0.0.1:8000/health
```

Also check `rag-frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

### MinIO bucket looks empty

New uploads are stored in the bucket for the selected knowledge base. Milvus uses MinIO internally too, so you may see a bucket that belongs to Milvus and another bucket used by myAgent documents.
