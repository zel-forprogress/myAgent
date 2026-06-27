# myAgent

myAgent 是一个本地 RAG Agent 项目，围绕 FastAPI、LangGraph、Milvus、PostgreSQL、MinIO、Next.js 和 Langfuse 构建。项目支持文档入库、多知识库检索、聊天会话持久化、流式回答、Agent 执行链路观测，以及用于知识库管理的后台页面。

## 功能特性

- 基于 Qwen / DashScope 的 OpenAI-compatible API 调用
- 基于 LangGraph 的 Agent 工作流
- 支持流式输出回答
- 支持多知识库选择与检索
- 支持 `.txt`、`.md`、`.pdf`、`.docx` 文档上传与解析
- 使用 Milvus 存储向量并进行语义检索
- 使用 PostgreSQL 持久化用户、会话和消息数据
- 使用 MinIO 存储上传的原始文件
- 使用 Langfuse 观测 Agent 节点、检索结果和模型调用
- Next.js 前端，包含聊天页、登录页和管理后台
- 基础用户角色：管理员和普通用户

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
| 可观测性 | Langfuse |
| 前端 | Next.js, React, TypeScript |
| 本地依赖部署 | Docker Compose |

## 项目结构

```text
myAgent/
+-- .env.example             # 一键 Docker Compose 启动的环境变量模板
+-- docker-compose.yml       # 完整启动前端、后端和基础设施服务
+-- rag-backend/
|   +-- app/
|   |   +-- api/              # FastAPI 接口层
|   |   +-- core/             # 配置与数据库初始化
|   |   +-- models/           # SQLAlchemy 数据模型
|   |   +-- schemas/          # 请求/响应模型
|   |   +-- services/         # RAG、Graph、存储、认证、会话逻辑
|   +-- data/docs/            # 本地开发测试文档
|   +-- docs/                 # 后端相关笔记
|   +-- docker-compose.yml    # 仅启动 PostgreSQL、Milvus、MinIO、etcd，适合本地开发
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
```

## 快速启动

完整启动流程请看 [docs/STARTUP.md](docs/STARTUP.md)。

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
- MinIO 控制台：http://127.0.0.1:9001

停止完整系统：

```powershell
docker compose down
```

### 方式二：开发模式手动启动

适合你平时改代码：数据库、Milvus、MinIO 用 Docker 跑，后端和前端在本机启动。

后端简版流程：

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
copy .env.example .env
docker compose up -d
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端简版流程：

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

如果不是本地开发环境，请在 `rag-backend/.env` 中修改这些默认账号和密码。

## 常用开发命令

启动后端依赖服务：

```powershell
cd rag-backend
docker compose up -d
```

启动后端服务：

```powershell
cd rag-backend
uvicorn app.main:app --reload
```

启动前端服务：

```powershell
cd rag-frontend
npm run dev
```

停止 Docker 服务：

```powershell
cd rag-backend
docker compose down
```

## 注意事项

- 不要提交 `.env` 或 `.env.local`，它们里面会包含真实密钥。
- 根目录 `.env.example` 用于完整 Docker Compose 启动。
- 后端环境变量模板是 `rag-backend/.env.example`。
- 前端环境变量模板是 `rag-frontend/.env.local.example`。
- 上传的原始文件会进入 MinIO。
- 解析后的文本 chunk 会进入 Milvus。
- 用户、会话、消息等结构化数据会进入 PostgreSQL。
- 如果 `3000` 端口被占用，Next.js 可能会自动切换到 `3001` 等其他端口。
