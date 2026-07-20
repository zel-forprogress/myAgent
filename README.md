# myAgent

myAgent 是一个本地 RAG Agent 项目，围绕 FastAPI、LangGraph、Milvus、PostgreSQL、MinIO、Redis、Celery、Next.js 和 Langfuse 构建。项目支持多知识库问答、会话记忆、上下文补全、上下文压缩、异步文档入库、入库 Pipeline 节点日志、检索测试、Rerank、后台管理和 Agent 执行链路观测。

## 功能特性

- 基于 Qwen / DashScope 的 OpenAI-compatible API 调用。
- 基于 LangGraph 的 Agent 工作流，包含问题补全、意图分析、检索、改写、回答生成等节点。
- 支持会话持久化、会话记忆、上下文压缩和 `standalone_question` 上下文补全。
- 支持普通回答和流式回答。
- 支持多知识库创建、选择、检索和管理。
- 支持 `.txt`、`.md`、`.pdf`、`.docx`、Office、HTML 和常见图片文件上传与解析。
- 支持 Docling / Azure Document Intelligence / basic 三种文档解析路径。
- 使用 Milvus 存储向量并进行语义检索，同时维护 PostgreSQL 中的文档与 chunk 元数据。
- 支持可选 Rerank，并在后台提供 Rerank 开关和检索测试能力。
- 使用 MinIO 存储上传的原始文件。
- 使用 Redis + Celery 执行异步入库任务，支持任务排队、重试和取消。
- 支持入库 Pipeline 节点日志，可查看每次入库的状态、节点、耗时、chunks、跳过数量和错误信息。
- 使用 Langfuse 观测 Agent 节点、检索结果、模型调用和关键中间结果。
- Next.js 前端，包含聊天页、登录页和管理后台。
- 基础用户角色：管理员和普通用户。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 后端 | Python, FastAPI, Uvicorn |
| Agent 编排 | LangGraph |
| RAG 组件 | LangChain |
| 模型调用 | OpenAI-compatible API, DashScope/Qwen |
| 向量数据库 | Milvus |
| 关系型数据库 | PostgreSQL |
| 对象存储 | MinIO |
| 异步任务 | Redis, Celery |
| 文档解析 | Docling, Azure Document Intelligence, pypdf |
| 可观测性 | Langfuse |
| 前端 | Next.js, React, TypeScript |
| 本地依赖部署 | Docker Compose |

## 核心流程

### 聊天问答

```text
用户问题
  -> 读取会话历史和记忆摘要
  -> LangGraph complete_question_with_history 节点生成 standalone_question
  -> 判断问题类型和检索策略
  -> 多知识库检索 Milvus
  -> 可选 Rerank
  -> 生成回答
  -> 保存用户消息、AI 消息、检索结果和中间状态
  -> Langfuse 记录链路
```

会话记忆策略：

- 16 条消息以内：使用完整历史。
- 超过 16 条：生成并维护会话摘要。
- 后续提问：使用摘要 + 最近 8 条原始消息。
- 摘要最长约 600 字，用于降低长对话 token 消耗。

### 文档入库

```text
上传或注册文档
  -> 创建 IngestionTask
  -> 写入 pending 文档记录
  -> Redis / Celery 排队
  -> inspect_document
  -> chunk_embed_index
  -> update_document_record
  -> 更新任务状态
  -> 记录每个节点日志
```

管理后台可以查看最近入库任务，包括任务状态、当前节点、文件名、知识库、chunks、跳过数量、失败原因和节点耗时。任务支持失败后重试，也支持取消排队中或执行中的入库任务。

## 项目结构

```text
myAgent/
+-- .env.example             # 一键 Docker Compose 启动的环境变量模板
+-- docker-compose.yml       # 完整启动前端、后端、worker 和基础设施服务
+-- rag-backend/
|   +-- app/
|   |   +-- api/              # FastAPI 接口层
|   |   +-- core/             # 配置、数据库、Celery 初始化
|   |   +-- models/           # SQLAlchemy 数据模型
|   |   +-- schemas/          # 请求/响应模型
|   |   +-- services/         # RAG、Graph、存储、认证、入库、会话逻辑
|   |   +-- tasks/            # Celery 异步任务
|   +-- data/docs/            # 本地开发测试文档
|   +-- docs/                 # 后端相关笔记
|   +-- docker-compose.yml    # 仅启动后端依赖服务，适合本地开发
|   +-- Dockerfile            # 后端镜像构建文件
|   +-- requirements.txt
+-- rag-frontend/
|   +-- app/                  # Next.js 页面
|   +-- components/           # 公共组件
|   +-- lib/                  # 前端 API / 认证工具
|   +-- Dockerfile            # 前端镜像构建文件
|   +-- package.json
+-- docs/
    +-- STARTUP.md            # 本地启动说明
    +-- DEPLOYMENT.md         # Docker Compose 部署说明
```

## 快速启动

完整启动流程请看 [docs/STARTUP.md](docs/STARTUP.md)。如果要用 Docker Compose 做完整部署，请看 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

### 方式一：Docker Compose 一键启动

适合演示、联调、交付和接近生产的本地运行方式。

```powershell
cd D:\code\git_localRepository\myAgent
copy .env.example .env
```

打开根目录 `.env`，至少填写：

```env
OPENAI_API_KEY=your_dashscope_api_key
```

然后启动完整系统：

```powershell
docker compose up -d --build
```

常用访问地址：

- 前端页面：http://localhost:3000
- 后端 Swagger：http://127.0.0.1:8000/docs
- 后端健康检查：http://127.0.0.1:8000/health
- MinIO 控制台：http://127.0.0.1:9001
- Docling 服务：http://127.0.0.1:5001

停止完整系统：

```powershell
docker compose down
```

### 方式二：开发模式手动启动

适合平时改代码：PostgreSQL、Redis、Milvus、MinIO 等依赖用 Docker 跑，后端、worker 和前端在本机启动。

后端依赖服务：

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
copy .env.example .env
docker compose up -d
```

后端 API：

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

异步入库 worker：

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
celery -A app.core.celery_app.celery_app worker -Q ingestion --loglevel=INFO
```

前端：

```powershell
cd D:\code\git_localRepository\myAgent\rag-frontend
copy .env.local.example .env.local
npm install
npm run dev
```

## 默认账号

后端启动时会自动初始化两个本地测试账号：

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 管理员 | `admin` | `admin123456` |
| 普通用户 | `demo` | `demo123456` |

如果不是本地开发环境，请在 `rag-backend/.env` 或根目录 `.env` 中修改这些默认账号和密码。

## 常用开发命令

运行后端测试：

```powershell
cd rag-backend
pytest -q
```

构建前端：

```powershell
cd rag-frontend
npm run build
```

启动后端依赖服务：

```powershell
cd rag-backend
docker compose up -d
```

停止后端依赖服务：

```powershell
cd rag-backend
docker compose down
```

查看完整 Docker Compose 日志：

```powershell
docker compose logs -f backend worker frontend
```

## 主要接口

- `POST /auth/login`：登录。
- `GET /auth/me`：获取当前用户。
- `GET /knowledge-bases`：查询知识库。
- `POST /knowledge-bases`：创建知识库。
- `POST /sessions`：创建聊天会话。
- `GET /sessions`：查询会话列表。
- `POST /sessions/{session_id}/chat/stream`：会话内流式问答。
- `POST /chat`：兼容的直接问答接口。
- `POST /ingest/upload`：上传文档并创建异步入库任务。
- `POST /ingest`：注册已有文档并创建异步入库任务。
- `GET /ingestion/tasks`：查询入库任务列表。
- `GET /ingestion/tasks/{task_id}`：查询入库任务详情和节点日志。
- `POST /ingestion/tasks/{task_id}/retry`：重试失败或取消的入库任务。
- `POST /ingestion/tasks/{task_id}/cancel`：取消 pending、queued、running 或 retrying 任务。
- `POST /retrieval/test`：后台检索测试。
- `GET /admin/settings/rerank`：查看 Rerank 设置。
- `PUT /admin/settings/rerank`：更新 Rerank 开关。
- `GET /stats`：后台统计数据。
- `GET /health`：依赖健康检查。

## 环境变量说明

根目录 `.env.example` 用于完整 Docker Compose 启动，主要包含：

- 模型配置：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`CHAT_MODEL`、`EMBEDDING_MODEL`。
- 存储配置：`OBJECT_STORAGE_*`、`S3_*`。
- 认证配置：`AUTH_SECRET_KEY`、`AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`、默认种子账号。
- 可观测配置：`LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_BASE_URL`。
- 异步入库配置：`REDIS_URL`、`CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND`、`INGESTION_TASK_MAX_RETRIES`。
- Rerank 配置：`RERANK_ENABLED`、`RERANK_MODEL`、`RERANK_BASE_URL`。
- 文档解析配置：`DOCUMENT_PARSER`、`DOCLING_*`、`AZURE_DOCUMENT_INTELLIGENCE_*`。
- 前端 API 地址：`NEXT_PUBLIC_API_BASE_URL`。

## 注意事项

- 不要提交 `.env` 或 `.env.local`，它们里面会包含真实密钥。
- 根目录 `.env.example` 用于完整 Docker Compose 启动。
- 后端环境变量模板是 `rag-backend/.env.example`。
- 前端环境变量模板是 `rag-frontend/.env.local.example`。
- 上传的原始文件会进入 MinIO。
- 解析后的文本 chunk 会进入 Milvus，文档和 chunk 元数据会进入 PostgreSQL。
- 用户、会话、消息、会话摘要、入库任务和节点日志等结构化数据会进入 PostgreSQL。
- 异步入库依赖 Redis 和 Celery worker；如果 worker 没有启动，任务会停留在 pending 或 queued 状态。
- 如果启用 Langfuse，需要填写有效的 Langfuse 地址和密钥。
- 如果 `3000` 端口被占用，Next.js 可能会自动切换到 `3001` 等其他端口。
