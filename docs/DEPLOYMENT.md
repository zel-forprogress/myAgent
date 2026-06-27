# 部署说明

这份文档用于说明如何用 Docker Compose 启动完整的 myAgent 系统，并给出生产化部署时需要注意的配置项。

## 1. 服务组成

根目录 `docker-compose.yml` 会启动以下服务：

| 服务 | 作用 | 默认端口 |
| --- | --- | --- |
| `frontend` | Next.js 前端页面 | `3000` |
| `backend` | FastAPI 后端接口 | `8000` |
| `postgres` | 用户、会话、消息、知识库元数据 | `5433 -> 5432` |
| `milvus` | 向量数据库 | `19530` |
| `minio` | 对象存储，保存上传原始文件 | `9000`、`9001` |
| `etcd` | Milvus 依赖的元数据服务 | 容器内访问 |

## 2. 环境变量

首次部署时，在项目根目录执行：

```powershell
copy .env.example .env
```

至少需要修改：

```env
OPENAI_API_KEY=your_dashscope_api_key
```

建议生产环境也修改这些值：

```env
AUTH_SECRET_KEY=replace-with-a-long-random-secret
SEED_ADMIN_PASSWORD=replace-with-a-strong-password
SEED_USER_PASSWORD=replace-with-a-strong-password
```

如果需要 Langfuse 观测，填写：

```env
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TIMEOUT=30
```

## 3. 一键启动

在项目根目录执行：

```powershell
docker compose up -d --build
```

查看服务状态：

```powershell
docker compose ps
```

查看后端日志：

```powershell
docker compose logs -f backend
```

停止服务：

```powershell
docker compose down
```

如果只想停止容器但保留数据卷，不要加 `-v`。加上 `-v` 会删除 PostgreSQL、Milvus、MinIO 等服务的数据卷。

## 4. 访问地址

默认访问地址：

- 前端页面：`http://localhost:3000`
- 后端 Swagger：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`
- MinIO 控制台：`http://127.0.0.1:9001`

MinIO 默认账号：

```text
username: minioadmin
password: minioadmin
```

如果部署到服务器，需要把 `NEXT_PUBLIC_API_BASE_URL` 改成浏览器可以访问到的后端地址，例如：

```env
NEXT_PUBLIC_API_BASE_URL=https://api.example.com
```

修改后需要重新构建前端镜像：

```powershell
docker compose up -d --build frontend
```

## 5. 健康检查

访问：

```text
http://127.0.0.1:8000/health
```

正常时会返回：

```json
{
  "status": "ok",
  "services": {
    "api": {
      "status": "ok"
    },
    "postgres": {
      "status": "ok"
    },
    "milvus": {
      "status": "ok"
    },
    "object_storage": {
      "status": "ok"
    }
  }
}
```

如果 PostgreSQL、Milvus 或 MinIO 中任意一个不可用，接口会返回 HTTP `503`，并把整体状态标记为 `degraded`。

## 6. 数据卷

根目录 Compose 使用以下数据卷：

| 数据卷 | 存储内容 |
| --- | --- |
| `postgres_data` | 用户、会话、消息、知识库元数据 |
| `milvus_data` | Milvus 向量数据 |
| `minio_data` | 上传的原始文档 |
| `etcd_data` | Milvus 依赖的 etcd 数据 |

生产环境不要随意执行：

```powershell
docker compose down -v
```

这会删除所有数据卷。

## 7. 备份建议

建议定期备份三类数据：

- PostgreSQL：备份结构化业务数据。
- MinIO：备份上传的原始文件。
- Milvus：备份向量数据和索引数据。

最小可用备份策略：

1. 定期导出 PostgreSQL。
2. 定期备份 MinIO bucket。
3. 保留 Milvus 和 etcd 数据卷快照。

## 8. 常见部署问题

### 前端能打开，但接口请求失败

检查根目录 `.env`：

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

如果不是本机访问，需要改成实际可访问的后端地址。

### `/health` 返回 degraded

查看具体是哪一个服务失败：

```powershell
docker compose logs -f backend
docker compose ps
```

如果是 MinIO 或 Milvus 问题，优先确认 Docker 服务是否全部启动完成。

### 修改环境变量后没有生效

后端环境变量修改后，重启后端：

```powershell
docker compose up -d --force-recreate backend
```

前端的 `NEXT_PUBLIC_API_BASE_URL` 会在构建时写入页面包，修改后需要重新构建：

```powershell
docker compose up -d --build frontend
```
