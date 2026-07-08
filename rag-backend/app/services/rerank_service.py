from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings
from app.schemas import SourceChunk


@dataclass
class RerankResult:
    sources: list[SourceChunk]
    applied: bool
    error: str = ""


def _rerank_url() -> str:
    if settings.rerank_base_url:
        return settings.rerank_base_url.rstrip("/")
    return f"{settings.openai_base_url.rstrip('/')}/reranks"


def _extract_rerank_index(item: dict) -> int | None:
    value = item.get("index")
    if isinstance(value, int):
        return value

    document = item.get("document")
    if isinstance(document, dict) and isinstance(document.get("index"), int):
        return document["index"]
    return None


def _extract_rerank_score(item: dict) -> float | None:
    for key in ("relevance_score", "score"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def rerank_sources(
    *,
    question: str,
    sources: list[SourceChunk],
    top_k: int,
) -> RerankResult:
    if not sources:
        return RerankResult(sources=sources, applied=False)

    payload = {
        "model": settings.rerank_model,
        "query": question,
        "documents": [source.content for source in sources],
        "top_n": min(max(top_k, 1), len(sources)),
        "return_documents": False,
    }
    request = Request(
        _rerank_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=settings.rerank_timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return RerankResult(
            sources=sources[:top_k],
            applied=False,
            error=f"Rerank request failed: HTTP {exc.code} {detail[:300]}",
        )
    except URLError as exc:
        return RerankResult(
            sources=sources[:top_k],
            applied=False,
            error=f"Rerank request failed: {exc.reason}",
        )
    except Exception as exc:
        return RerankResult(
            sources=sources[:top_k],
            applied=False,
            error=f"Rerank request failed: {exc}",
        )

    try:
        data = json.loads(body)
        results = data.get("results") or data.get("data") or []
    except Exception as exc:
        return RerankResult(
            sources=sources[:top_k],
            applied=False,
            error=f"Rerank response parse failed: {exc}",
        )

    ranked: list[SourceChunk] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        index = _extract_rerank_index(item)
        score = _extract_rerank_score(item)
        if index is None or score is None or index < 0 or index >= len(sources):
            continue
        source = sources[index]
        source.rerank_score = score
        source.score = score
        ranked.append(source)

    if not ranked:
        return RerankResult(
            sources=sources[:top_k],
            applied=False,
            error="Rerank response did not include valid results.",
        )

    return RerankResult(sources=ranked[:top_k], applied=True)
