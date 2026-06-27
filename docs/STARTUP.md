# 本地启动说明

这份文档用于说明如何从一个干净的本地仓库启动 myAgent。

## 1. 前置环境

请先安装：

- Docker Desktop
- Python 3.11 或更高版本
- Conda 或其他 Python 虚拟环境工具
- Node.js 20 或更高版本
- npm

本项目通过 Docker Compose 启动以下本地依赖服务：

- PostgreSQL
- etcd
- MinIO
- Milvus

## 2. 配置后端环境变量

进入后端目录并创建 `.env`：

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
copy .env.example .env
```

打开 `rag-backend/.env`，把 `OPENAI_API_KEY` 改成你自己的 DashScope / Qwen API Key：

```env
OPENAI_API_KEY=your_dashscope_api_key
```

当前项目通过 DashScope 的 OpenAI-compatible endpoint 调用模型：

```env
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
CHAT_MODEL=qwen3.7-plus
EMBEDDING_MODEL=text-embedding-v4
```

如果你使用其他 Qwen 聊天模型，只需要修改 `CHAT_MODEL`。

## 3. 启动 Docker 依赖服务

在后端目录执行：

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
docker compose up -d
```

查看容器状态：

```powershell
docker compose ps
```

本地服务地址：

- Milvus：`localhost:19530`
- PostgreSQL：`localhost:5433`
- MinIO API：`http://127.0.0.1:9000`
- MinIO 控制台：`http://127.0.0.1:9001`

MinIO 本地账号：

```text
username: minioadmin
password: minioadmin
```

## 4. 安装后端依赖

创建并激活 Python 虚拟环境：

```powershell
conda create -n rag-agent python=3.11 -y
conda activate rag-agent
```

安装依赖：

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
pip install -r requirements.txt
```

## 5. 启动后端

在 `rag-backend` 目录启动 FastAPI：

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
uvicorn app.main:app --reload
```

打开 Swagger：

```text
http://127.0.0.1:8000/docs
```

健康检查接口：

```text
GET http://127.0.0.1:8000/health
```

正常返回：

```json
{
  "status": "ok"
}
```

## 6. 配置前端环境变量

进入前端目录并创建 `.env.local`：

```powershell
cd D:\code\git_localRepository\myAgent\rag-frontend
copy .env.local.example .env.local
```

默认后端地址：

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## 7. 安装并启动前端

安装前端依赖：

```powershell
cd D:\code\git_localRepository\myAgent\rag-frontend
npm install
```

启动 Next.js：

```powershell
npm run dev
```

打开前端页面：

```text
http://localhost:3000
```

如果 `3000` 端口已经被占用，Next.js 可能会自动使用 `3001`。以终端输出的地址为准。

## 8. 登录账号

默认测试账号：

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 管理员 | `admin` | `admin123456` |
| 普通用户 | `demo` | `demo123456` |

管理员可以进入管理后台。普通用户只能使用聊天页面。

## 9. 基础测试流程

1. 打开 `http://localhost:3000`。
2. 使用 `admin` 登录。
3. 进入管理后台。
4. 创建一个知识库。
5. 点击知识库名称进入文档管理页面。
6. 上传 `.txt`、`.md`、`.pdf` 或 `.docx` 文件。
7. 打开 MinIO，确认原始文件已经写入对应 bucket。
8. 在管理后台确认文档列表和 chunk 数正常。
9. 返回聊天首页。
10. 选择知识库范围，提问一个和上传文档相关的问题。
11. 检查回答、检索来源、执行步骤是否正常展示。

## 10. Langfuse 配置

Langfuse 是可选配置。如果这些字段为空，核心 RAG 功能仍然可以运行。

```env
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TIMEOUT=30
```

填写后需要重启后端服务。然后发送一次聊天请求，在 Langfuse 的 Tracing 页面确认是否能看到 trace、span 和 generation。

## 11. 常见问题

### Docker 拉取镜像失败

如果出现 `failed to fetch oauth token`、`EOF` 等错误，通常是网络问题。可以稍后重试：

```powershell
docker compose up -d
```

### Docker daemon 没有启动

先打开 Docker Desktop，再执行：

```powershell
docker compose up -d
```

### 后端报 `No module named 'app'`

通常是启动目录不对。需要在 `rag-backend` 目录执行：

```powershell
cd D:\code\git_localRepository\myAgent\rag-backend
uvicorn app.main:app --reload
```

### 前端显示 Connection error

先确认后端是否正常运行：

```text
http://127.0.0.1:8000/health
```

再检查 `rag-frontend/.env.local`：

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

### MinIO 中看不到刚上传的文件

每个知识库会对应自己的对象存储 bucket。请确认你打开的是当前知识库对应的 bucket。Milvus 自己也会依赖 MinIO，因此 MinIO 里可能同时存在 Milvus 使用的 bucket 和 myAgent 上传文档使用的 bucket。
