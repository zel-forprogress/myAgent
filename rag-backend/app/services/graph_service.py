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
from app.services.settings_service import get_rerank_enabled

MIN_RETRIEVAL_SCORE = 0.45


class ChatState(TypedDict):
    question: str
    chat_history: str
    standalone_question: str
    rewritten_question: str
    top_k: int
    collection_names: List[str]
    route: str
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


def append_step(state: ChatState, step: str) -> List[str]:
    return [*state.get("steps", []), step]


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
                "你是一个严格的问题路由器。你的任务是判断用户问题是否需要查询当前知识库。"
                "当前系统是知识库问答系统，默认优先使用知识库检索。"
                "你只能输出 rag 或 direct，不要解释。",
            ),
            (
                "human",
                "判断规则:\n"
                "- 只要问题是在询问知识、概念、说明、介绍、总结、对比、原理、作用、用途、文档内容等，优先输出 rag。\n"
                "- 如果问题涉及已上传文档、知识库内容、项目、技术栈、系统实现、架构、LangGraph、Milvus、RAG、Qwen、FastAPI 等内容，必须输出 rag。\n"
                "- 只有在问题是纯问候、寒暄、自我介绍这类明显不需要检索的内容时，才输出 direct。\n"
                "- 不要因为问题看起来像通用知识就输出 direct；知识库系统默认先检索再回答。\n\n"
                "用户问题: {question}\n\n"
                "请只输出 rag 或 direct。",
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
        route = normalize_route(response.content, question)
    except Exception:
        route = keyword_route(question)

    return {"route": route, "steps": append_step(state, "analyze_question")}


def route_question(state: ChatState) -> str:
    return state["route"]


def retrieve(state: ChatState) -> dict:
    sources = retrieve_with_optional_rerank(state, retrieval_question(state))
    return {"sources": sources, "steps": append_step(state, "retrieve")}


def check_retrieval_quality(state: ChatState) -> dict:
    retrieval_quality = "good"
    if max_source_score(state.get("sources", [])) < MIN_RETRIEVAL_SCORE:
        retrieval_quality = "poor"
    return {
        "retrieval_quality": retrieval_quality,
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
        "steps": append_step(state, "rewrite_question"),
    }


def retrieve_rewritten(state: ChatState) -> dict:
    query = state.get("rewritten_question") or state["question"]
    sources = retrieve_with_optional_rerank(state, query)
    return {"sources": sources, "steps": append_step(state, "retrieve_rewritten")}


def check_rewritten_quality(state: ChatState) -> dict:
    retrieval_quality = "rewritten_good"
    if max_source_score(state.get("sources", [])) < MIN_RETRIEVAL_SCORE:
        retrieval_quality = "rewritten_poor"
    return {
        "retrieval_quality": retrieval_quality,
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
    return {"answer": answer, "steps": append_step(state, "generate_rag_answer")}


def generate_no_context_answer(state: ChatState) -> dict:
    return {
        "answer": "资料里没有找到足够相关的内容，暂时无法基于知识库回答这个问题。",
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
                "如果资料中没有答案，请直接说资料中没有提到。",
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

    return {"answer": answer, "steps": append_step(state, "generate_rag_answer")}


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
        "steps": append_step(state, "generate_direct_answer"),
    }


def chat_with_graph_stream(
    collection_names: List[str],
    question: str,
    top_k: int,
    chat_history: str,
    on_event: Callable[[dict[str, Any]], None],
) -> tuple[str, List[SourceChunk], str, List[str], str, str, str]:
    state: ChatState = {
        "question": question,
        "chat_history": chat_history,
        "standalone_question": question,
        "rewritten_question": "",
        "top_k": top_k,
        "collection_names": collection_names,
        "route": "",
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
                    "retrieval_quality": state.get("retrieval_quality", ""),
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

    run_regular_node("complete_question_with_history", complete_question_with_history)
    run_regular_node("analyze_question", analyze_question)

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
    )


def build_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node(
        "complete_question_with_history",
        traced_node("complete_question_with_history", complete_question_with_history),
    )
    graph.add_node("analyze_question", traced_node("analyze_question", analyze_question))
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
    graph.add_conditional_edges(
        "analyze_question",
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
) -> tuple[str, List[SourceChunk], str, List[str], str, str, str]:
    result = chat_graph.invoke(
        {
            "question": question,
            "chat_history": chat_history,
            "standalone_question": question,
            "rewritten_question": "",
            "top_k": top_k,
            "collection_names": collection_names,
            "route": "",
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
    )
