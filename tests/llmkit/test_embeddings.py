import asyncio
import json
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from haussmann.llmkit.embeddings import (
    EmbeddingMiss,
    Embeddings,
    EmbeddingsClient,
    ReplayEmbedder,
    embedding_key,
)

REPLY = {
    "data": [{"index": 1, "embedding": [0.0, 1.0]}, {"index": 0, "embedding": [1.0, 0.0]}],
    "usage": {"prompt_tokens": 7, "cost": 0.0000001},
}


def embed(handler: httpx.MockTransport, texts: Sequence[str]) -> Embeddings:
    async def run() -> Embeddings:
        async with httpx.AsyncClient(transport=handler) as http:
            return await EmbeddingsClient("https://host/v1", "secret", http).embed("model-e", texts)

    return asyncio.run(run())


def test_client_sends_the_texts_and_returns_vectors_in_input_order() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=REPLY)

    result = embed(httpx.MockTransport(handler), ["a", "b"])
    (sent,) = seen
    assert str(sent.url) == "https://host/v1/embeddings"
    assert sent.headers["authorization"] == "Bearer secret"
    assert json.loads(sent.content) == {
        "model": "model-e",
        "input": ["a", "b"],
        "encoding_format": "float",
    }
    assert result == Embeddings(((1.0, 0.0), (0.0, 1.0)), 7, Decimal("0.0000001"))


def test_a_reply_with_the_wrong_number_of_vectors_raises() -> None:
    with pytest.raises(ValueError, match="expected 3"):
        embed(httpx.MockTransport(lambda _: httpx.Response(200, json=REPLY)), ["a", "b", "c"])


def test_an_error_status_raises() -> None:
    with pytest.raises(httpx.HTTPStatusError):
        embed(httpx.MockTransport(lambda _: httpx.Response(500)), ["a"])


class Counting:
    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, model: str, texts: Sequence[str]) -> Embeddings:
        self.calls += 1
        return Embeddings(tuple((float(len(t)), 1.0) for t in texts), 3)


def test_record_then_replay_returns_the_same_vectors(tmp_path: Path) -> None:
    live = Counting()
    recorded = asyncio.run(ReplayEmbedder(tmp_path, live).embed("model-e", ["a", "bb"]))
    replayed = asyncio.run(ReplayEmbedder(tmp_path).embed("model-e", ["a", "bb"]))
    assert replayed == recorded
    assert live.calls == 1


def test_a_miss_without_an_inner_embedder_raises(tmp_path: Path) -> None:
    with pytest.raises(EmbeddingMiss):
        asyncio.run(ReplayEmbedder(tmp_path).embed("model-e", ["a"]))


def test_key_depends_on_model_texts_and_their_order() -> None:
    base = embedding_key("model-e", ["a", "b"])
    assert base == embedding_key("model-e", ["a", "b"])
    assert base != embedding_key("model-f", ["a", "b"])
    assert base != embedding_key("model-e", ["b", "a"])
    assert base != embedding_key("model-e", ["ab"])
