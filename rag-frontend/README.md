# rag-frontend

最小可用的 Next.js 前端，用来调用 `rag-backend` 的聊天和文档管理接口。

## 启动

1. 安装依赖

```bash
npm install
```

2. 配置环境变量

```bash
copy .env.local.example .env.local
```

3. 启动开发服务器

```bash
npm run dev
```

默认地址：

```text
http://localhost:3000
```

## 当前功能

- 首页 `/`
  - 提问并调用 `/chat`
  - 展示 answer
  - 展示 route / retrieval_quality
  - 展示 steps
  - 展示 sources
- 后台 `/admin`
  - 查看 `/health`
  - 查看 `/documents`
  - 调用 `/ingest`
  - 调用 `DELETE /documents`
