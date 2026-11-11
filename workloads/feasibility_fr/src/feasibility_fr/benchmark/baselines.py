"""The two baseline systems: everything in one prompt, and retrieve-then-prompt."""

import datetime as dt
import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from feasibility_fr.benchmark.answer import (
    INSTRUCTIONS,
    InvalidAnswer,
    answer_schema,
    parse_answer,
    render_pages,
    render_questions,
)
from feasibility_fr.engine.spec import RequiredFact
from haussmann.coretypes.values import Schema
from haussmann.docparse.elements import Element
from haussmann.evalkit.scorer import Submission
from haussmann.llmkit.client import LLMClient, Message, Request, Response
from haussmann.llmkit.embeddings import Embedder, Vector

ANSWER_MAX_TOKENS = 6000
TOP_K = 3


@dataclass(frozen=True, slots=True)
class Attempt:
    """`submission` is None and `failure` says why when the answer could not be read."""

    submission: Submission | None
    failure: str | None
    responses: tuple[Response, ...]
    embedding_cost_usd: Decimal = Decimal(0)


def build_request(
    pages: Sequence[Element],
    asked: Sequence[RequiredFact],
    schema: Schema,
    model: str,
    sample: int,
    as_of: dt.date,
) -> Request:
    user = (
        f"Date of this review: {as_of.isoformat()}\n\n"
        f"Questions:\n{render_questions(asked, schema)}\n\nDocuments:\n\n{render_pages(pages)}"
    )
    return Request(
        model=model,
        messages=(Message("system", INSTRUCTIONS), Message("user", user)),
        max_tokens=ANSWER_MAX_TOKENS,
        temperature=0.0,
        seed=sample,
        output_schema=answer_schema(schema),
    )


async def _ask(
    pages: Sequence[Element],
    asked: Sequence[RequiredFact],
    schema: Schema,
    client: LLMClient,
    model: str,
    sample: int,
    as_of: dt.date,
) -> Attempt:
    request = build_request(pages, asked, schema, model, sample, as_of)
    response = await client.complete(request, sample=sample)
    try:
        return Attempt(parse_answer(response.text, schema), None, (response,))
    except InvalidAnswer as error:
        reason = f"{response.stop_reason}: {error}".splitlines()[0]
        return Attempt(None, reason, (response,))


async def one_prompt(
    pages: Sequence[Element],
    asked: Sequence[RequiredFact],
    schema: Schema,
    client: LLMClient,
    model: str,
    sample: int,
    as_of: dt.date,
) -> Attempt:
    """Baseline (a): every page and every question in a single call."""
    return await _ask(pages, asked, schema, client, model, sample, as_of)


def cosine(left: Vector, right: Vector) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norms = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norms if norms else 0.0


def retrieve(queries: Sequence[Vector], pages: Sequence[Vector], top_k: int) -> list[int]:
    """Indices of the `top_k` most similar pages for each query, merged, in page order."""
    kept: set[int] = set()
    for query in queries:
        ranked = sorted(range(len(pages)), key=lambda i: (-cosine(query, pages[i]), i))
        kept.update(ranked[:top_k])
    return sorted(kept)


async def naive_rag(
    pages: Sequence[Element],
    asked: Sequence[RequiredFact],
    schema: Schema,
    client: LLMClient,
    embedder: Embedder,
    model: str,
    embedding_model: str,
    sample: int,
    as_of: dt.date,
    top_k: int = TOP_K,
) -> Attempt:
    """Baseline (b): embed questions and pages, keep the closest pages, then a single call."""
    texts = [question.text for question in asked] + [page.text for page in pages]
    embedded = await embedder.embed(embedding_model, texts)
    queries, page_vectors = embedded.vectors[: len(asked)], embedded.vectors[len(asked) :]
    selected = [pages[index] for index in retrieve(queries, page_vectors, top_k)]
    attempt = await _ask(selected, asked, schema, client, model, sample, as_of)
    return Attempt(
        attempt.submission,
        attempt.failure,
        attempt.responses,
        embedded.reported_cost_usd or Decimal(0),
    )
