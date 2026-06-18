# Agent Graph

本文档记录阶段 2 中 `/chat` 接口的 LangGraph 工作流。

## 目标

阶段 1 的 `/chat` 是固定 RAG 流程：

```text
用户问题 -> Milvus 检索 -> 拼接上下文 -> Qwen 回答
```

阶段 2 将它升级为 Agent 工作流：

```text
用户问题 -> 路由判断 -> 检索 / 直接回答 -> 检索质量判断 -> 问题改写 -> 二次检索 -> 回答
```

核心目标：

- 判断用户问题是否需要查询知识库
- 对 RAG 检索结果进行质量判断
- 检索质量差时自动改写问题并重试
- 返回执行路径，方便调试 Agent 流程

## 流程图

```text
START
  |
  v
analyze_question
  |
  +-- direct ----------------------+
  |                                |
  v                                v
generate_direct_answer            END

  |
  +-- rag
       |
       v
     retrieve
       |
       v
     check_retrieval_quality
       |
       +-- good -> generate_rag_answer -> END
       |
       +-- poor
             |
             v
          rewrite_question
             |
             v
          retrieve_rewritten
             |
             v
          check_rewritten_quality
             |
             +-- rewritten_good -> generate_rag_answer -> END
             |
             +-- rewritten_poor -> generate_no_context_answer -> END
```

## 节点说明

### analyze_question

判断用户问题是否需要查询知识库。

输出：

```text
route = rag | direct
```

当前实现优先使用 Qwen 判断。如果模型调用失败或返回不规范，则使用关键词规则兜底。

### generate_direct_answer

处理不需要查询知识库的问题，例如问候、闲聊、通用问题。

特点：

```text
不访问 Milvus
sources 为空
retrieval_quality = not_applicable
```

### retrieve

使用原始用户问题查询 Milvus。

输出：

```text
sources
```

每个 source 包含：

```text
content
source
score
```

### check_retrieval_quality

根据检索结果的最高 `score` 判断检索质量。

当前阈值：

```text
MIN_RETRIEVAL_SCORE = 0.45
```

输出：

```text
retrieval_quality = good | poor
```

### rewrite_question

当第一次检索质量较差时，调用 Qwen 改写用户问题，使其更适合知识库检索。

输出：

```text
rewritten_question
```

### retrieve_rewritten

使用 `rewritten_question` 再次查询 Milvus。

### check_rewritten_quality

判断二次检索结果质量。

输出：

```text
retrieval_quality = rewritten_good | rewritten_poor
```

### generate_rag_answer

基于检索到的 `sources` 生成知识库回答。

### generate_no_context_answer

当原始问题和改写问题都没有检索到足够相关内容时，返回兜底回答。

## 状态字段

LangGraph 中的核心状态：

```text
question             原始用户问题
rewritten_question   改写后的问题
top_k                检索片段数量
route                路由结果：rag / direct
retrieval_quality    检索质量判断结果
sources              检索到的知识片段
answer               最终回答
steps                已执行节点列表
```

## /chat 响应字段

`/chat` 返回：

```json
{
  "answer": "最终回答",
  "sources": [],
  "route": "rag",
  "steps": [],
  "retrieval_quality": "good",
  "rewritten_question": ""
}
```

字段说明：

```text
answer               最终回答
sources              检索片段，包含 content/source/score
route                本次走 rag 还是 direct
steps                本次经过了哪些 LangGraph 节点
retrieval_quality    检索质量：good/poor/rewritten_good/rewritten_poor/not_applicable
rewritten_question   如果触发问题改写，这里返回改写后的问题
```

## 测试用例

### 知识库问题

请求：

```json
{
  "question": "LangGraph 在本项目中负责什么？",
  "top_k": 4
}
```

期望：

```text
route = rag
sources 非空
steps 包含 retrieve
```

可能路径：

```text
analyze_question
retrieve
check_retrieval_quality
generate_rag_answer
```

### 普通问题

请求：

```json
{
  "question": "你好，你是谁？",
  "top_k": 4
}
```

期望：

```text
route = direct
sources = []
retrieval_quality = not_applicable
```

可能路径：

```text
analyze_question
generate_direct_answer
```

### 检索质量不足的问题

请求：

```json
{
  "question": "这个系统里谁负责控制流程走向？",
  "top_k": 4
}
```

可能路径：

```text
analyze_question
retrieve
check_retrieval_quality
rewrite_question
retrieve_rewritten
check_rewritten_quality
generate_rag_answer
```

如果二次检索仍然不足：

```text
generate_no_context_answer
```

## 阶段 2 完成情况

阶段 2 已完成：

- 接入 LangGraph
- 支持 rag/direct 分支
- 支持 LLM Router
- 支持 steps 执行轨迹
- 支持 sources score
- 支持检索质量判断
- 支持问题改写和二次检索

下一阶段建议：

```text
阶段 3：接入 Langfuse，对 Agent 节点、模型调用和检索结果做观测。
```
