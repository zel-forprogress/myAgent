# Langfuse Observability

本文档记录阶段 3：Langfuse 观测接入。

## 目标

在 `/chat` 请求执行时，把整个 Agent 工作流的运行过程记录到 Langfuse，便于排查问题和观察执行路径。

希望观测到三层信息：

```text
1. trace：一次完整的 /chat 请求
2. span：Agent / LangGraph 每个节点的执行情况
3. generation：大模型调用的输入、输出、token 使用情况
```

## 配置项

`.env` 中增加：

```env
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TIMEOUT=30
```

字段说明：

```text
LANGFUSE_PUBLIC_KEY   Langfuse 项目公钥
LANGFUSE_SECRET_KEY   Langfuse 项目私钥
LANGFUSE_BASE_URL     Langfuse 服务地址
LANGFUSE_TIMEOUT      Langfuse SDK 请求超时时间
```

## 接入方式

### 1. 在 /chat 外层增加 trace

在 `app/main.py` 的 `/chat` 接口外层创建一条总 trace，用来表示一次完整问答请求。

记录内容包括：

```text
question
top_k
最终 answer
route
steps
retrieval_quality
rewritten_question
sources
```

### 2. 在 LangGraph 节点增加 span

在每个关键节点执行时记录 span，例如：

```text
analyze_question
retrieve
check_retrieval_quality
rewrite_question
retrieve_rewritten
check_rewritten_quality
generate_rag_answer
generate_direct_answer
```

作用：

```text
看到每个节点有没有执行
看到节点输入输出
看到最终流程到底走了哪条路径
```

### 3. 在模型调用位置增加 generation

在调用 Qwen 的地方增加 generation，例如：

```text
qwen_router_call
qwen_rewrite_call
qwen_direct_answer_call
qwen_rag_answer_call
```

作用：

```text
记录模型输入
记录模型输出
记录 token 使用情况
记录本次调用属于哪个节点
```

## 测试过程中遇到的问题

### 问题 1：Langfuse 中有时看不到最新请求

现象：

```text
/chat 已经返回成功
但 Langfuse 页面里没有对应 trace
```

原因：

```text
不是接口没执行
而是本地 Langfuse 客户端向 Langfuse 云端上报 trace 时发生了超时
本次实际排查时，超时报错表现为 5s
```

解决方式：

```text
给 Langfuse SDK 增加 timeout 配置
并在 .env 中设置 LANGFUSE_TIMEOUT=30
```

结论：

```text
之前不是没埋点，而是 trace 没有成功上报
调整超时时间后，Langfuse 可以稳定看到最新观测数据
```

## 当前观测结果

当前 Langfuse 已经可以看到 `/chat` 的完整执行链路，例如：

```text
chat
analyze question
qwen router call
retrieve
check retrieval quality
rewrite question
qwen rewrite call
retrieve rewritten
check rewritten quality
generate rag answer
qwen rag answer call
```

这说明：

```text
1. 总 trace 已经正常记录
2. 各个 Agent 节点 span 已经正常记录
3. 模型调用 generation 已经正常记录
```

## 阶段 3 完成情况

阶段 3 已完成：

- 接入 Langfuse SDK
- 为 `/chat` 增加总 trace
- 为 LangGraph 节点增加 span
- 为模型调用增加 generation
- 解决 Langfuse 上报超时问题
- 成功在 Langfuse 页面看到完整链路

下一阶段建议：

```text
阶段 4：接前端，让前端页面真实调用 /chat、/documents、/ingest 等接口
```
