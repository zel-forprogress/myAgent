from typing import Any, Callable, List, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.schemas import SourceChunk
from app.services.observability import (
    extract_usage_details,
    start_generation,
    start_node_span,
    update_generation,
    update_node_span,
)
from app.services.rag_service import (
    build_context,
    generate_answer_with_context,
    get_llm,
    retrieve_sources_multi,
)
from app.services.rerank_service import rerank_sources
from app.services.settings_service import get_rerank_enabled, get_retrieval_min_score


class ChatState(TypedDict):
    question: str
    chat_history: str
    standalone_question: str
    rewritten_question: str
    top_k: int
    collection_names: List[str]
    route: str
    task_intent: str
    task_confidence: float
    agent_plan: List[str]
    tool_calls: List[dict[str, Any]]
    retrieval_quality: str
    sources: List[SourceChunk]
    answer: str
    steps: List[str]


DIRECT_PATTERNS = [
    "你好",
    "您好",
    "hi",
    "hello",
    "嗨",
    "你是谁",
    "你叫什么",
    "早上好",
    "中午好",
    "下午好",
    "晚上好",
    "谢谢",
    "感谢",
    "再见",
    "拜拜",
]

TASK_INTENTS = {
    "chat",
    "knowledge_qa",
    "summarize",
    "compare",
    "extract",
    "write",
    "tool",
}


def append_step(state: ChatState, step: str) -> List[str]:
    return [*state.get("steps", []), step]


def append_tool_call(
    state: ChatState,
    *,
    name: str,
    status: str = "success",
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [
        *state.get("tool_calls", []),
        {
            "name": name,
            "status": status,
            "input": input_data or {},
            "output": output_data or {},
        },
    ]


def max_source_score(sources: List[SourceChunk]) -> float:
    return max((source.score or 0.0 for source in sources), default=0.0)


def shorten_text(text: str, limit: int = 1000) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def serialize_value_for_span(value: Any) -> Any:
    if isinstance(value, SourceChunk):
        return {
            "source": value.source,
            "score": value.score,
            "content_preview": value.content[:200],
        }
    if isinstance(value, list):
        return [serialize_value_for_span(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_value_for_span(item) for key, item in value.items()}
    if isinstance(value, str):
        return shorten_text(value)
    return value


def state_snapshot_for_span(state: ChatState) -> dict[str, Any]:
    sources = state.get("sources", [])
    return {
        "question": state.get("question", ""),
        "has_chat_history": bool(state.get("chat_history", "")),
        "standalone_question": state.get("standalone_question", ""),
        "rewritten_question": state.get("rewritten_question", ""),
        "top_k": state.get("top_k", 4),
        "collection_names": state.get("collection_names", []),
        "collection_count": len(state.get("collection_names", [])),
        "route": state.get("route", ""),
        "task_intent": state.get("task_intent", ""),
        "task_confidence": state.get("task_confidence", 0.0),
        "agent_plan": state.get("agent_plan", []),
        "tool_call_count": len(state.get("tool_calls", [])),
        "retrieval_quality": state.get("retrieval_quality", ""),
        "source_count": len(sources),
        "max_source_score": max_source_score(sources),
        "steps": state.get("steps", []),
    }


def traced_node(name: str, node: Callable[[ChatState], dict]) -> Callable[[ChatState], dict]:
    def wrapped(state: ChatState) -> dict:
        with start_node_span(name, input_data=state_snapshot_for_span(state)) as span:
            result = node(state)
            update_node_span(
                span,
                output=serialize_value_for_span(result),
                metadata={"node": name, "result_keys": list(result.keys())},
            )
            return result

    return wrapped


def is_direct_question(question: str) -> bool:
    normalized_question = question.strip().lower()
    if not normalized_question:
        return True

    return any(pattern in normalized_question for pattern in DIRECT_PATTERNS)


def keyword_route(question: str) -> str:
    if is_direct_question(question):
        return "direct"
    return "rag"


def keyword_task_intent(question: str) -> str:
    normalized_question = question.strip().lower()
    if is_direct_question(normalized_question):
        return "chat"
    if any(word in normalized_question for word in ["总结", "概括", "归纳", "梳理"]):
        return "summarize"
    if any(word in normalized_question for word in ["对比", "比较", "区别", "差异"]):
        return "compare"
    if any(word in normalized_question for word in ["抽取", "提取", "列出", "字段", "清单"]):
        return "extract"
    if any(word in normalized_question for word in ["写", "生成", "起草", "方案", "报告"]):
        return "write"
    return "knowledge_qa"


def normalize_task_intent(raw_intent: str, question: str) -> str:
    normalized_intent = raw_intent.strip().lower().replace("-", "_")
    if normalized_intent in TASK_INTENTS:
        return normalized_intent
    if normalized_intent in {"direct", "smalltalk", "casual"}:
        return "chat"
    if normalized_intent in {"rag", "qa", "question_answering", "knowledge"}:
        return "knowledge_qa"
    return keyword_task_intent(question)


def route_from_task_intent(task_intent: str) -> str:
    return "direct" if task_intent == "chat" else "rag"


def normalize_route(raw_route: str, question: str) -> str:
    route = raw_route.strip().lower()
    if route == "rag" or route.startswith("rag"):
        return "rag"
    if route == "direct" or route.startswith("direct"):
        return "direct"
    return keyword_route(question)


def extract_stream_text(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content or "")


def retrieval_question(state: ChatState) -> str:
    return state.get("rewritten_question") or state.get("standalone_question") or state["question"]


def retrieve_with_optional_rerank(state: ChatState, question: str) -> List[SourceChunk]:
    top_k = state["top_k"]
    candidate_top_k = top_k
    rerank_enabled = get_rerank_enabled()
    if rerank_enabled:
        candidate_top_k = min(
            max(top_k * max(1, settings.rerank_candidate_multiplier), top_k),
            50,
        )

    sources = retrieve_sources_multi(
        collection_names=state["collection_names"],
        question=question,
        top_k=candidate_top_k,
    )

    if not rerank_enabled:
        return sources[:top_k]

    rerank_result = rerank_sources(
        question=question,
        sources=sources,
        top_k=top_k,
    )
    return rerank_result.sources


def complete_question_with_history(state: ChatState) -> dict:
    question = state["question"].strip()
    chat_history = state.get("chat_history", "").strip()
    if not question:
        return {
            "standalone_question": question,
            "steps": append_step(state, "complete_question_with_history"),
        }
    if not chat_history or is_direct_question(question):
        return {
            "standalone_question": question,
            "steps": append_step(state, "complete_question_with_history"),
        }

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是对话上下文补全器。请根据历史对话，把用户当前问题改写成一个语义完整、"
                "离开上下文也能理解的独立问题。不要回答问题，不要解释。"
                "如果当前问题本身已经完整，请原样返回。不得编造历史中没有的实体或条件。",
            ),
            (
                "human",
                "历史对话:\n{chat_history}\n\n当前问题:\n{question}\n\n独立问题:",
            ),
        ]
    )

    try:
        with start_generation(
            "qwen_context_completion_call",
            input_data={"question": question, "chat_history": shorten_text(chat_history)},
            model=settings.chat_model,
            model_parameters={"temperature": 0},
            metadata={"node": "complete_question_with_history"},
        ) as generation:
            response = (prompt | get_llm()).invoke(
                {"chat_history": chat_history, "question": question}
            )
            update_generation(
                generation,
                output=response.content,
                usage_details=extract_usage_details(response),
            )
        standalone_question = str(response.content).strip() or question
    except Exception:
        standalone_question = question

    return {
        "standalone_question": standalone_question,
        "steps": append_step(state, "complete_question_with_history"),
    }


def analyze_question(state: ChatState) -> dict:
    question = state.get("standalone_question") or state["question"]
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是 Agentic RAG 的任务意图路由器。你的任务是判断用户当前请求属于哪类任务。"
                "只能输出一个标签，不要解释。可选标签: "
                "chat, knowledge_qa, summarize, compare, extract, write, tool。",
            ),
            (
                "human",
                "分类规则:\n"
                "- chat: 纯问候、寒暄、感谢、自我介绍，不需要知识库。\n"
                "- knowledge_qa: 基于知识库回答概念、说明、要求、流程、原因、用途等问题。\n"
                "- summarize: 总结、概括、归纳一个或多个文档/主题。\n"
                "- compare: 对比多个对象、方案、文档或差异。\n"
                "- extract: 抽取字段、清单、表格、要求、时间、数字、条款。\n"
                "- write: 基于资料写报告、方案、邮件、计划、文案。\n"
                "- tool: 明确要求执行外部动作或调用业务系统/API。\n\n"
                "默认原则: 除 chat 外，其它任务都需要知识库或工具上下文。\n\n"
                "用户问题: {question}\n\n"
                "请只输出一个标签。",
            ),
        ]
    )

    try:
        with start_generation(
            "qwen_router_call",
            input_data={"question": question},
            model=settings.chat_model,
            model_parameters={"temperature": 0},
            metadata={"node": "analyze_question"},
        ) as generation:
            response = (prompt | get_llm()).invoke({"question": question})
            update_generation(
                generation,
                output=response.content,
                usage_details=extract_usage_details(response),
            )
        task_intent = normalize_task_intent(str(response.content), question)
    except Exception:
        task_intent = keyword_task_intent(question)

    route = route_from_task_intent(task_intent)
    task_confidence = 0.95 if task_intent == keyword_task_intent(question) else 0.75
    return {
        "route": route,
        "task_intent": task_intent,
        "task_confidence": task_confidence,
        "steps": append_step(state, "analyze_question"),
    }


def route_question(state: ChatState) -> str:
    return state["route"]


def plan_for_intent(task_intent: str) -> list[str]:
    if task_intent == "chat":
        return ["直接理解用户输入", "给出简洁回复"]
    if task_intent == "summarize":
        return ["扩大召回相关片段", "筛选高相关来源", "按主题归纳总结"]
    if task_intent == "compare":
        return ["召回候选材料", "识别对比对象", "按差异维度组织答案"]
    if task_intent == "extract":
        return ["召回包含结构化信息的片段", "抽取字段与清单", "保持来源可追溯"]
    if task_intent == "write":
        return ["召回事实依据", "整理写作要点", "生成可交付文本"]
    if task_intent == "tool":
        return ["识别需要调用的工具", "执行工具并检查结果", "汇总工具输出"]
    return ["理解问题", "检索知识库", "检查检索质量", "基于资料生成回答"]


def plan_agent_task(state: ChatState) -> dict:
    task_intent = state.get("task_intent", "knowledge_qa")
    plan = plan_for_intent(task_intent)
    return {
        "agent_plan": plan,
        "tool_calls": append_tool_call(
            state,
            name="agent_planner",
            input_data={
                "task_intent": task_intent,
                "route": state.get("route", ""),
                "question": state.get("standalone_question") or state["question"],
            },
            output_data={"plan": plan},
        ),
        "steps": append_step(state, "plan_agent_task"),
    }


def retrieve(state: ChatState) -> dict:
    sources = retrieve_with_optional_rerank(state, retrieval_question(state))
    return {
        "sources": sources,
        "tool_calls": append_tool_call(
            state,
            name="knowledge_retrieval",
            input_data={
                "question": retrieval_question(state),
                "top_k": state["top_k"],
                "collections": state["collection_names"],
            },
            output_data={
                "source_count": len(sources),
                "max_score": max_source_score(sources),
                "rerank_applied": any(source.rerank_score is not None for source in sources),
            },
        ),
        "steps": append_step(state, "retrieve"),
    }


def check_retrieval_quality(state: ChatState) -> dict:
    retrieval_quality = "good"
    max_score = max_source_score(state.get("sources", []))
    min_score = get_retrieval_min_score()
    if max_score < min_score:
        retrieval_quality = "poor"
    return {
        "retrieval_quality": retrieval_quality,
        "tool_calls": append_tool_call(
            state,
            name="retrieval_quality_check",
            input_data={"max_score": max_score, "min_required_score": min_score},
            output_data={"retrieval_quality": retrieval_quality},
        ),
        "steps": append_step(state, "check_retrieval_quality"),
    }


def route_retrieval_quality(state: ChatState) -> str:
    return state["retrieval_quality"]


def rewrite_question(state: ChatState) -> dict:
    base_question = state.get("standalone_question") or state["question"]
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一个检索 query 改写器。你的任务是把用户问题改写成更适合在当前项目知识库中检索的查询。"
                "只输出改写后的查询，不要解释。",
            ),
            (
                "human",
                "原始问题: {question}\n\n"
                "请改写成更适合检索项目文档、技术栈、架构、LangGraph、Milvus、RAG 等内容的查询。",
            ),
        ]
    )

    try:
        with start_generation(
            "qwen_rewrite_call",
            input_data={"question": state["question"]},
            model=settings.chat_model,
            model_parameters={"temperature": 0},
            metadata={"node": "rewrite_question"},
        ) as generation:
            response = (prompt | get_llm()).invoke({"question": base_question})
            update_generation(
                generation,
                output=response.content,
                usage_details=extract_usage_details(response),
            )
        rewritten_question = response.content.strip()
    except Exception:
        rewritten_question = base_question

    if not rewritten_question:
        rewritten_question = base_question

    return {
        "rewritten_question": rewritten_question,
        "tool_calls": append_tool_call(
            state,
            name="query_rewriter",
            input_data={"question": base_question},
            output_data={"rewritten_question": rewritten_question},
        ),
        "steps": append_step(state, "rewrite_question"),
    }


def retrieve_rewritten(state: ChatState) -> dict:
    query = state.get("rewritten_question") or state["question"]
    sources = retrieve_with_optional_rerank(state, query)
    return {
        "sources": sources,
        "tool_calls": append_tool_call(
            state,
            name="knowledge_retrieval",
            input_data={
                "question": query,
                "top_k": state["top_k"],
                "collections": state["collection_names"],
                "rewritten": True,
            },
            output_data={
                "source_count": len(sources),
                "max_score": max_source_score(sources),
                "rerank_applied": any(source.rerank_score is not None for source in sources),
            },
        ),
        "steps": append_step(state, "retrieve_rewritten"),
    }


def check_rewritten_quality(state: ChatState) -> dict:
    retrieval_quality = "rewritten_good"
    max_score = max_source_score(state.get("sources", []))
    min_score = get_retrieval_min_score()
    if max_score < min_score:
        retrieval_quality = "rewritten_poor"
    return {
        "retrieval_quality": retrieval_quality,
        "tool_calls": append_tool_call(
            state,
            name="retrieval_quality_check",
            input_data={"max_score": max_score, "min_required_score": min_score, "rewritten": True},
            output_data={"retrieval_quality": retrieval_quality},
        ),
        "steps": append_step(state, "check_rewritten_quality"),
    }


def route_rewritten_quality(state: ChatState) -> str:
    return state["retrieval_quality"]


def generate_rag_answer(state: ChatState) -> dict:
    answer = generate_answer_with_context(
        question=state["question"],
        sources=state.get("sources", []),
        chat_history=state.get("chat_history", ""),
        standalone_question=state.get("standalone_question", ""),
    )
    return {
        "answer": answer,
        "tool_calls": append_tool_call(
            state,
            name="answer_generator",
            input_data={
                "source_count": len(state.get("sources", [])),
                "retrieval_quality": state.get("retrieval_quality", ""),
            },
            output_data={"answer_length": len(answer)},
        ),
        "steps": append_step(state, "generate_rag_answer"),
    }


def generate_no_context_answer(state: ChatState) -> dict:
    answer = "资料里没有找到足够相关的内容，暂时无法基于知识库回答这个问题。"
    return {
        "answer": answer,
        "tool_calls": append_tool_call(
            state,
            name="no_context_guard",
            input_data={"retrieval_quality": state.get("retrieval_quality", "")},
            output_data={"guarded": True, "answer_length": len(answer)},
        ),
        "steps": append_step(state, "generate_no_context_answer"),
    }


def generate_direct_answer(state: ChatState) -> dict:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一个简洁友好的助手。当前问题不需要查询知识库，请结合必要的历史对话直接回答。",
            ),
            ("human", "历史对话:\n{chat_history}\n\n当前问题:\n{question}"),
        ]
    )
    chain = prompt | get_llm()
    with start_generation(
        "qwen_direct_answer_call",
        input_data={"question": state["question"]},
        model=settings.chat_model,
        model_parameters={"temperature": 0},
        metadata={"node": "generate_direct_answer"},
    ) as generation:
        response = chain.invoke(
            {
                "chat_history": state.get("chat_history", "") or "无",
                "question": state["question"],
            }
        )
        update_generation(
            generation,
            output=response.content,
            usage_details=extract_usage_details(response),
        )

    return {
        "answer": response.content,
        "sources": [],
        "retrieval_quality": "not_applicable",
        "tool_calls": append_tool_call(
            state,
            name="direct_answer_generator",
            input_data={"question": state["question"]},
            output_data={"answer_length": len(str(response.content))},
        ),
        "steps": append_step(state, "generate_direct_answer"),
    }


def stream_rag_answer(
    state: ChatState,
    on_token: Callable[[str], None],
) -> dict:
    context = build_context(state.get("sources", []))

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一个严谨的知识库问答助手。请只根据给定资料回答问题。"
                "历史对话只用于理解用户当前表达，不得替代资料作为事实来源。"
                "当前已经通过检索质量检查，说明资料中存在可用相关内容；不要只回答“资料中没有提到”。"
                "如果资料没有直接覆盖用户问题，但包含相关流程、条件、步骤、认证、考试或注意事项，"
                "请先明确说明资料未直接提到原问题的某一具体方面，再概括这些相关内容。"
                "只有在资料完全没有相关内容时，才说资料中没有提到。",
            ),
            ("human", "资料:\n{context}\n\n问题: {question}"),
        ]
    )

    chain = prompt | get_llm()
    answer_parts: list[str] = []

    with start_generation(
        "qwen_rag_answer_call",
        input_data={
            "question": state["question"],
            "context": context,
            "source_count": len(state.get("sources", [])),
        },
        model=settings.chat_model,
        model_parameters={"temperature": 0},
        metadata={"node": "generate_rag_answer"},
    ) as generation:
        for chunk in chain.stream(
            {
                "context": context,
                "question": (
                    f"历史对话:\n{state.get('chat_history', '') or '无'}\n\n"
                    f"用户原始问题: {state['question']}\n"
                    f"补全后的问题: {state.get('standalone_question') or state['question']}"
                ),
            }
        ):
            text = extract_stream_text(chunk)
            if not text:
                continue
            answer_parts.append(text)
            on_token(text)

        answer = "".join(answer_parts)
        update_generation(generation, output=answer)

    return {
        "answer": answer,
        "tool_calls": append_tool_call(
            state,
            name="answer_generator",
            input_data={
                "source_count": len(state.get("sources", [])),
                "retrieval_quality": state.get("retrieval_quality", ""),
            },
            output_data={"answer_length": len(answer)},
        ),
        "steps": append_step(state, "generate_rag_answer"),
    }


def stream_direct_answer(
    state: ChatState,
    on_token: Callable[[str], None],
) -> dict:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一个简洁友好的助手。当前问题不需要查询知识库，请结合必要的历史对话直接回答。",
            ),
            ("human", "历史对话:\n{chat_history}\n\n当前问题:\n{question}"),
        ]
    )
    chain = prompt | get_llm()
    answer_parts: list[str] = []

    with start_generation(
        "qwen_direct_answer_call",
        input_data={"question": state["question"]},
        model=settings.chat_model,
        model_parameters={"temperature": 0},
        metadata={"node": "generate_direct_answer"},
    ) as generation:
        for chunk in chain.stream(
            {
                "chat_history": state.get("chat_history", "") or "无",
                "question": state["question"],
            }
        ):
            text = extract_stream_text(chunk)
            if not text:
                continue
            answer_parts.append(text)
            on_token(text)

        answer = "".join(answer_parts)
        update_generation(generation, output=answer)

    return {
        "answer": answer,
        "sources": [],
        "retrieval_quality": "not_applicable",
        "tool_calls": append_tool_call(
            state,
            name="direct_answer_generator",
            input_data={"question": state["question"]},
            output_data={"answer_length": len(answer)},
        ),
        "steps": append_step(state, "generate_direct_answer"),
    }


def chat_with_graph_stream(
    collection_names: List[str],
    question: str,
    top_k: int,
    chat_history: str,
    on_event: Callable[[dict[str, Any]], None],
) -> tuple[
    str,
    List[SourceChunk],
    str,
    List[str],
    str,
    str,
    str,
    str,
    float,
    List[str],
    list[dict[str, Any]],
]:
    state: ChatState = {
        "question": question,
        "chat_history": chat_history,
        "standalone_question": question,
        "rewritten_question": "",
        "top_k": top_k,
        "collection_names": collection_names,
        "route": "",
        "task_intent": "",
        "task_confidence": 0.0,
        "agent_plan": [],
        "tool_calls": [],
        "retrieval_quality": "",
        "sources": [],
        "answer": "",
        "steps": [],
    }

    def run_regular_node(name: str, func: Callable[[ChatState], dict[str, Any]]) -> None:
        nonlocal state
        on_event({"type": "step", "data": {"step": name, "status": "start"}})
        result = traced_node(name, func)(state)
        state = {**state, **result}
        on_event(
            {
                "type": "step",
                "data": {
                    "step": name,
                    "status": "done",
                    "route": state.get("route", ""),
                    "task_intent": state.get("task_intent", ""),
                    "task_confidence": state.get("task_confidence", 0.0),
                    "retrieval_quality": state.get("retrieval_quality", ""),
                    "agent_plan": state.get("agent_plan", []),
                    "tool_calls": state.get("tool_calls", []),
                },
            }
        )
        if name in {"retrieve", "retrieve_rewritten"}:
            on_event(
                {
                    "type": "sources",
                    "data": {
                        "sources": [
                            source.model_dump() if hasattr(source, "model_dump") else source
                            for source in state.get("sources", [])
                        ]
                    },
                }
            )
        if name == "rewrite_question" and state.get("rewritten_question"):
            on_event(
                {
                    "type": "meta",
                    "data": {
                        "rewritten_question": state.get("rewritten_question", ""),
                    },
                }
            )
        if name == "complete_question_with_history" and state.get("standalone_question"):
            on_event(
                {
                    "type": "meta",
                    "data": {
                        "standalone_question": state.get("standalone_question", ""),
                    },
                }
            )
        if name == "plan_agent_task":
            on_event(
                {
                    "type": "meta",
                    "data": {
                        "agent_plan": state.get("agent_plan", []),
                        "tool_calls": state.get("tool_calls", []),
                    },
                }
            )

    run_regular_node("complete_question_with_history", complete_question_with_history)
    run_regular_node("analyze_question", analyze_question)
    run_regular_node("plan_agent_task", plan_agent_task)

    if state["route"] == "direct":
        on_event({"type": "step", "data": {"step": "generate_direct_answer", "status": "start"}})
        result = stream_direct_answer(
            state,
            lambda text: on_event({"type": "token", "data": {"content": text}}),
        )
        state = {**state, **result}
        on_event({"type": "step", "data": {"step": "generate_direct_answer", "status": "done"}})
    else:
        run_regular_node("retrieve", retrieve)
        run_regular_node("check_retrieval_quality", check_retrieval_quality)

        if state["retrieval_quality"] == "poor":
            run_regular_node("rewrite_question", rewrite_question)
            run_regular_node("retrieve_rewritten", retrieve_rewritten)
            run_regular_node("check_rewritten_quality", check_rewritten_quality)

        if state["retrieval_quality"] == "rewritten_poor":
            on_event(
                {
                    "type": "step",
                    "data": {"step": "generate_no_context_answer", "status": "start"},
                }
            )
            result = generate_no_context_answer(state)
            state = {**state, **result}
            answer = state["answer"]
            for chunk_text in [answer[i : i + 24] for i in range(0, len(answer), 24)]:
                on_event({"type": "token", "data": {"content": chunk_text}})
            on_event(
                {
                    "type": "step",
                    "data": {"step": "generate_no_context_answer", "status": "done"},
                }
            )
        else:
            on_event({"type": "step", "data": {"step": "generate_rag_answer", "status": "start"}})
            result = stream_rag_answer(
                state,
                lambda text: on_event({"type": "token", "data": {"content": text}}),
            )
            state = {**state, **result}
            on_event({"type": "step", "data": {"step": "generate_rag_answer", "status": "done"}})

    return (
        state["answer"],
        state.get("sources", []),
        state.get("route", ""),
        state.get("steps", []),
        state.get("retrieval_quality", ""),
        state.get("rewritten_question", ""),
        state.get("standalone_question", ""),
        state.get("task_intent", ""),
        state.get("task_confidence", 0.0),
        state.get("agent_plan", []),
        state.get("tool_calls", []),
    )


def build_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node(
        "complete_question_with_history",
        traced_node("complete_question_with_history", complete_question_with_history),
    )
    graph.add_node("analyze_question", traced_node("analyze_question", analyze_question))
    graph.add_node("plan_agent_task", traced_node("plan_agent_task", plan_agent_task))
    graph.add_node("retrieve", traced_node("retrieve", retrieve))
    graph.add_node(
        "check_retrieval_quality",
        traced_node("check_retrieval_quality", check_retrieval_quality),
    )
    graph.add_node("rewrite_question", traced_node("rewrite_question", rewrite_question))
    graph.add_node("retrieve_rewritten", traced_node("retrieve_rewritten", retrieve_rewritten))
    graph.add_node(
        "check_rewritten_quality",
        traced_node("check_rewritten_quality", check_rewritten_quality),
    )
    graph.add_node("generate_rag_answer", traced_node("generate_rag_answer", generate_rag_answer))
    graph.add_node(
        "generate_no_context_answer",
        traced_node("generate_no_context_answer", generate_no_context_answer),
    )
    graph.add_node(
        "generate_direct_answer",
        traced_node("generate_direct_answer", generate_direct_answer),
    )

    graph.add_edge(START, "complete_question_with_history")
    graph.add_edge("complete_question_with_history", "analyze_question")
    graph.add_edge("analyze_question", "plan_agent_task")
    graph.add_conditional_edges(
        "plan_agent_task",
        route_question,
        {"rag": "retrieve", "direct": "generate_direct_answer"},
    )
    graph.add_edge("retrieve", "check_retrieval_quality")
    graph.add_conditional_edges(
        "check_retrieval_quality",
        route_retrieval_quality,
        {"good": "generate_rag_answer", "poor": "rewrite_question"},
    )
    graph.add_edge("rewrite_question", "retrieve_rewritten")
    graph.add_edge("retrieve_rewritten", "check_rewritten_quality")
    graph.add_conditional_edges(
        "check_rewritten_quality",
        route_rewritten_quality,
        {"rewritten_good": "generate_rag_answer", "rewritten_poor": "generate_no_context_answer"},
    )
    graph.add_edge("generate_rag_answer", END)
    graph.add_edge("generate_no_context_answer", END)
    graph.add_edge("generate_direct_answer", END)
    return graph.compile()


chat_graph = build_chat_graph()


def chat_with_graph(
    collection_names: List[str],
    question: str,
    top_k: int = 4,
    chat_history: str = "",
) -> tuple[
    str,
    List[SourceChunk],
    str,
    List[str],
    str,
    str,
    str,
    str,
    float,
    List[str],
    list[dict[str, Any]],
]:
    result = chat_graph.invoke(
        {
            "question": question,
            "chat_history": chat_history,
            "standalone_question": question,
            "rewritten_question": "",
            "top_k": top_k,
            "collection_names": collection_names,
            "route": "",
            "task_intent": "",
            "task_confidence": 0.0,
            "agent_plan": [],
            "tool_calls": [],
            "retrieval_quality": "",
            "sources": [],
            "answer": "",
            "steps": [],
        }
    )
    return (
        result["answer"],
        result.get("sources", []),
        result.get("route", ""),
        result.get("steps", []),
        result.get("retrieval_quality", ""),
        result.get("rewritten_question", ""),
        result.get("standalone_question", ""),
        result.get("task_intent", ""),
        result.get("task_confidence", 0.0),
        result.get("agent_plan", []),
        result.get("tool_calls", []),
    )
