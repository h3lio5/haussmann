"""Text embeddings: one call contract, a live client and a replay cache."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import BaseModel, TypeAdapter

type Vector = tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Embeddings:
    """One vector per input text, in input order."""

    vectors: tuple[Vector, ...]
    input_tokens: int
    reported_cost_usd: Decimal | None = None


class Embedder(Protocol):
    async def embed(self, model: str, texts: Sequence[str]) -> Embeddings: ...


class _ItemWire(BaseModel):
    index: int
    embedding: list[float]


class _UsageWire(BaseModel):
    prompt_tokens: int = 0
    cost: Decimal | None = None


class _ReplyWire(BaseModel):
    data: list[_ItemWire]
    usage: _UsageWire = _UsageWire()


def parse_embeddings(content: bytes, expected: int) -> Embeddings:
    reply = _ReplyWire.model_validate_json(content)
    ordered = sorted(reply.data, key=lambda item: item.index)
    if [item.index for item in ordered] != list(range(expected)):
        raise ValueError(f"expected {expected} embeddings, got {len(ordered)}")
    return Embeddings(
        vectors=tuple(tuple(item.embedding) for item in ordered),
        input_tokens=reply.usage.prompt_tokens,
        reported_cost_usd=reply.usage.cost,
    )


class EmbeddingsClient:
    """`base_url` ends before `/embeddings`, for example `https://host/v1`."""

    def __init__(self, base_url: str, api_key: str, http: httpx.AsyncClient) -> None:
        self._url = f"{base_url.rstrip('/')}/embeddings"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._http = http

    async def embed(self, model: str, texts: Sequence[str]) -> Embeddings:
        body = {"model": model, "input": list(texts), "encoding_format": "float"}
        reply = await self._http.post(self._url, headers=self._headers, json=body)
        reply.raise_for_status()
        return parse_embeddings(reply.content, len(texts))


def embedding_key(model: str, texts: Sequence[str]) -> str:
    canonical = json.dumps([model, list(texts)], separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"v1\n{canonical}".encode()).hexdigest()


_EMBEDDINGS = TypeAdapter(Embeddings)


class EmbeddingMiss(KeyError):
    pass


class ReplayEmbedder:
    """Serves recorded vectors from `root`; on a miss calls `inner` and records, or raises."""

    def __init__(self, root: Path, inner: Embedder | None = None) -> None:
        self._root = root
        self._inner = inner

    async def embed(self, model: str, texts: Sequence[str]) -> Embeddings:
        key = embedding_key(model, texts)
        path = self._root / f"{key}.json"
        if path.exists():
            return _EMBEDDINGS.validate_json(path.read_bytes())
        if self._inner is None:
            raise EmbeddingMiss(f"no recorded embeddings for {model}: {key}")
        result = await self._inner.embed(model, texts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_EMBEDDINGS.dump_json(result))
        return result
