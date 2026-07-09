import logging
import json
import queue
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models import User
from app.schemas import ChatRequest, ChatResponse
from app.services.chat_store import (
    add_assistant_message,
    add_user_message,
    build_session_memory_context,
    get_chat_session,
)
from app.services.graph_service import chat_with_graph, chat_with_graph_stream
from app.services.knowledge_base_service import (
    resolve_knowledge_base,
    resolve_knowledge_bases,
)
from app.services.observability import start_chat_trace, update_chat_trace

router = APIRouter()
logger = logging.getLogger(__name__)


def run_chat(
    collection_names: list[str],
    knowledge_base_names: list[str],
    question: str,
    top_k: int,
    chat_history: str = "",
) -> ChatResponse:
    with start_chat_trace(question, top_k, knowledge_base_names) as trace:
        (
            answer,
            sources,
            route,
            steps,
            retrieval_quality,
            rewritten_question,
            standalone_question,
            task_intent,
            task_confidence,
            agent_plan,
            tool_calls,
        ) = chat_with_graph(
            collection_names=collection_names,
            question=question,
            top_k=top_k,
            chat_history=chat_history,
        )
        update_chat_trace(
            trace,
            answer=answer,
            sources=sources,
            route=route,
            steps=steps,
            retrieval_quality=retrieval_quality,
            rewritten_question=rewritten_question,
        )
    return ChatResponse(
        answer=answer,
        sources=sources,
        route=route,
        task_intent=task_intent,
        task_confidence=task_confidence,
        agent_plan=agent_plan,
        tool_calls=tool_calls,
        steps=steps,
        retrieval_quality=retrieval_quality,
        rewritten_question=rewritten_question,
        standalone_question=standalone_question,
    )


def encode_stream_event(event_type: str, data: dict[str, Any]) -> str:
    return json.dumps({"type": event_type, "data": data}, ensure_ascii=False) + "\n"


@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
def chat_in_session(
    session_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    try:
        session = get_chat_session(db, session_id, current_user)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if request.knowledge_base_ids is not None:
            knowledge_bases = resolve_knowledge_bases(db, request.knowledge_base_ids)
        elif request.knowledge_base_id:
            knowledge_bases = [resolve_knowledge_base(db, request.knowledge_base_id)]
        elif session.knowledge_base_id:
            knowledge_bases = [resolve_knowledge_base(db, session.knowledge_base_id)]
        else:
            knowledge_bases = resolve_knowledge_bases(db, None)

        chat_history = build_session_memory_context(db, session)
        add_user_message(db, session, request.question)
        response = run_chat(
            [item.collection_name for item in knowledge_bases],
            [item.name for item in knowledge_bases],
            request.question,
            request.top_k,
            chat_history,
        )
        add_assistant_message(
            db,
            session,
            content=response.answer,
            route=response.route,
            task_intent=response.task_intent,
            task_confidence=response.task_confidence,
            agent_plan=response.agent_plan,
            tool_calls=response.tool_calls,
            retrieval_quality=response.retrieval_quality,
            rewritten_question=response.rewritten_question,
            sources=response.sources,
            steps=response.steps,
            standalone_question=response.standalone_question,
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Session chat failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/chat/stream")
def chat_in_session_stream(
    session_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        session = get_chat_session(db, session_id, current_user)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if request.knowledge_base_ids is not None:
            knowledge_bases = resolve_knowledge_bases(db, request.knowledge_base_ids)
        elif request.knowledge_base_id:
            knowledge_bases = [resolve_knowledge_base(db, request.knowledge_base_id)]
        elif session.knowledge_base_id:
            knowledge_bases = [resolve_knowledge_base(db, session.knowledge_base_id)]
        else:
            knowledge_bases = resolve_knowledge_bases(db, None)

        chat_history = build_session_memory_context(db, session)
        add_user_message(db, session, request.question)
        collection_names = [item.collection_name for item in knowledge_bases]
        knowledge_base_names = [item.name for item in knowledge_bases]

        def streaming_wrapper():
            event_queue: queue.Queue[str | None] = queue.Queue()
            final_holder: dict[str, ChatResponse] = {}

            def worker() -> None:
                try:
                    with start_chat_trace(
                        request.question,
                        request.top_k,
                        knowledge_base_names,
                    ) as trace:
                        event_queue.put(
                            encode_stream_event(
                                "start",
                                {
                                    "session_id": session_id,
                                    "question": request.question,
                                    "top_k": request.top_k,
                                },
                            )
                        )

                        def emit(event: dict[str, Any]) -> None:
                            event_queue.put(
                                encode_stream_event(event["type"], event.get("data", {}))
                            )

                        (
                            answer,
                            sources,
                            route,
                            steps,
                            retrieval_quality,
                            rewritten_question,
            standalone_question,
            task_intent,
            task_confidence,
            agent_plan,
            tool_calls,
        ) = chat_with_graph_stream(
                            collection_names=collection_names,
                            question=request.question,
                            top_k=request.top_k,
                            chat_history=chat_history,
                            on_event=emit,
                        )

                        final_response = ChatResponse(
                            answer=answer,
                            sources=sources,
                            route=route,
                            task_intent=task_intent,
                            task_confidence=task_confidence,
                            agent_plan=agent_plan,
                            tool_calls=tool_calls,
                            steps=steps,
                            retrieval_quality=retrieval_quality,
                            rewritten_question=rewritten_question,
                            standalone_question=standalone_question,
                        )
                        final_holder["response"] = final_response
                        update_chat_trace(
                            trace,
                            answer=final_response.answer,
                            sources=final_response.sources,
                            route=final_response.route,
                            steps=final_response.steps,
                            retrieval_quality=final_response.retrieval_quality,
                            rewritten_question=final_response.rewritten_question,
                        )
                        event_queue.put(encode_stream_event("final", final_response.model_dump()))
                except Exception as exc:
                    logger.exception("Streaming session chat failed")
                    event_queue.put(encode_stream_event("error", {"message": str(exc)}))
                finally:
                    event_queue.put(None)

            thread = threading.Thread(target=worker, daemon=True)
            thread.start()

            while True:
                item = event_queue.get()
                if item is None:
                    break
                yield item

            final_response = final_holder.get("response")
            if final_response is not None:
                add_assistant_message(
                    db,
                    session,
                    content=final_response.answer,
                    route=final_response.route,
                    task_intent=final_response.task_intent,
                    task_confidence=final_response.task_confidence,
                    agent_plan=final_response.agent_plan,
                    tool_calls=final_response.tool_calls,
                    retrieval_quality=final_response.retrieval_quality,
                    rewritten_question=final_response.rewritten_question,
                    sources=final_response.sources,
                    steps=final_response.steps,
                    standalone_question=final_response.standalone_question,
                )

        return StreamingResponse(
            streaming_wrapper(),
            media_type="application/x-ndjson",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Session streaming chat setup failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    try:
        _ = current_user
        if request.knowledge_base_ids is not None:
            knowledge_bases = resolve_knowledge_bases(db, request.knowledge_base_ids)
        elif request.knowledge_base_id:
            knowledge_bases = [resolve_knowledge_base(db, request.knowledge_base_id)]
        else:
            knowledge_bases = resolve_knowledge_bases(db, None)
        return run_chat(
            [item.collection_name for item in knowledge_bases],
            [item.name for item in knowledge_bases],
            request.question,
            request.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
