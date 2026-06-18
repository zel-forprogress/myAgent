from contextlib import contextmanager
from typing import Any, Iterator, Optional

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover
    Langfuse = None

from app.core.config import settings
from app.schemas import SourceChunk

_langfuse_client = None


def get_langfuse_client():
    global _langfuse_client

    if _langfuse_client is not None:
        return _langfuse_client

    if Langfuse is None:
        return None

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    try:
        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url,
            timeout=settings.langfuse_timeout,
        )
    except Exception:
        return None

    return _langfuse_client


def safe_update_observation(observation: Any, **kwargs: Any) -> None:
    if observation is None:
        return

    try:
        observation.update(**kwargs)
    except Exception:
        pass


def flush_langfuse() -> None:
    client = get_langfuse_client()
    if client is None:
        return

    try:
        client.flush()
    except Exception:
        pass


@contextmanager
def start_node_span(
    name: str,
    *,
    input_data: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Optional[Any]]:
    client = get_langfuse_client()
    if client is None:
        yield None
        return

    manager = None
    observation = None
    exc_info = (None, None, None)

    try:
        manager = client.start_as_current_observation(as_type="span", name=name)
        observation = manager.__enter__()
        safe_update_observation(
            observation,
            input=input_data,
            metadata=metadata or {},
        )
    except Exception:
        yield None
        return

    try:
        yield observation
    except Exception as exc:
        exc_info = __import__("sys").exc_info()
        safe_update_observation(
            observation,
            output={"error": str(exc)},
            level="ERROR",
            status_message=str(exc),
        )
        raise
    finally:
        if manager is not None:
            try:
                manager.__exit__(*exc_info)
            except Exception:
                pass


def update_node_span(
    observation: Any,
    *,
    output: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    update_data: dict[str, Any] = {}
    if output is not None:
        update_data["output"] = output
    if metadata is not None:
        update_data["metadata"] = metadata
    if update_data:
        safe_update_observation(observation, **update_data)


def truncate_text(value: str, limit: int = 3000) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def serialize_for_observation(value: Any) -> Any:
    if isinstance(value, SourceChunk):
        return {
            "content": truncate_text(value.content),
            "source": value.source,
            "score": value.score,
        }
    if isinstance(value, list):
        return [serialize_for_observation(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_for_observation(item) for key, item in value.items()}
    if isinstance(value, str):
        return truncate_text(value)
    return value


@contextmanager
def start_generation(
    name: str,
    *,
    input_data: Any | None = None,
    model: str | None = None,
    model_parameters: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Optional[Any]]:
    client = get_langfuse_client()
    if client is None:
        yield None
        return

    manager = None
    observation = None
    exc_info = (None, None, None)

    try:
        manager = client.start_as_current_observation(
            as_type="generation",
            name=name,
            input=serialize_for_observation(input_data),
            model=model,
            model_parameters=model_parameters,
            metadata=metadata or {},
        )
        observation = manager.__enter__()
    except Exception:
        yield None
        return

    try:
        yield observation
    except Exception as exc:
        exc_info = __import__("sys").exc_info()
        safe_update_observation(
            observation,
            output={"error": str(exc)},
            level="ERROR",
            status_message=str(exc),
        )
        raise
    finally:
        if manager is not None:
            try:
                manager.__exit__(*exc_info)
            except Exception:
                pass


def extract_usage_details(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict):
        return {
            key: value
            for key, value in {
                "input": usage.get("input_tokens"),
                "output": usage.get("output_tokens"),
                "total": usage.get("total_tokens"),
            }.items()
            if isinstance(value, int)
        }

    response_metadata = getattr(response, "response_metadata", None)
    if not isinstance(response_metadata, dict):
        return None

    token_usage = response_metadata.get("token_usage") or response_metadata.get("usage")
    if not isinstance(token_usage, dict):
        return None

    return {
        key: value
        for key, value in {
            "input": token_usage.get("prompt_tokens") or token_usage.get("input_tokens"),
            "output": token_usage.get("completion_tokens") or token_usage.get("output_tokens"),
            "total": token_usage.get("total_tokens"),
        }.items()
        if isinstance(value, int)
    }


def update_generation(
    observation: Any,
    *,
    output: Any | None = None,
    usage_details: dict[str, int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    update_data: dict[str, Any] = {}
    if output is not None:
        update_data["output"] = serialize_for_observation(output)
    if usage_details:
        update_data["usage_details"] = usage_details
    if metadata is not None:
        update_data["metadata"] = metadata
    if update_data:
        safe_update_observation(observation, **update_data)


def serialize_sources(sources: list[SourceChunk]) -> list[dict[str, Any]]:
    return [source.model_dump() for source in sources]


@contextmanager
def start_chat_trace(
    question: str,
    top_k: int,
    knowledge_base_names: list[str] | None = None,
) -> Iterator[Optional[Any]]:
    client = get_langfuse_client()
    if client is None:
        yield None
        return

    manager = None
    observation = None
    exc_info = (None, None, None)

    try:
        manager = client.start_as_current_observation(as_type="span", name="chat")
        observation = manager.__enter__()
        safe_update_observation(
            observation,
            input={"question": question, "top_k": top_k},
            metadata={
                "endpoint": "/chat",
                "knowledge_base_names": knowledge_base_names or [],
                "knowledge_base_count": len(knowledge_base_names or []),
            },
        )
    except Exception:
        yield None
        return

    try:
        yield observation
    except Exception as exc:
        exc_info = __import__("sys").exc_info()
        safe_update_observation(
            observation,
            output={"error": str(exc)},
            level="ERROR",
            status_message=str(exc),
        )
        raise
    finally:
        if manager is not None:
            try:
                manager.__exit__(*exc_info)
            except Exception:
                pass
        flush_langfuse()


def update_chat_trace(
    observation: Any,
    *,
    answer: str,
    sources: list[SourceChunk],
    route: str,
    steps: list[str],
    retrieval_quality: str,
    rewritten_question: str,
) -> None:
    safe_update_observation(
        observation,
        output={"answer": answer},
        metadata={
            "route": route,
            "steps": steps,
            "retrieval_quality": retrieval_quality,
            "rewritten_question": rewritten_question,
            "sources": serialize_sources(sources),
        },
    )
