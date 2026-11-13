"""The journal in Postgres. Every statement the platform sends to the database is in this file."""

from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, LiteralString, cast

import psycopg
from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from haussmann.flow.journal import (
    InputsChanged,
    Json,
    RunLocked,
    RunState,
    StepCost,
    StepRepeated,
    summarize,
)
from haussmann.ledger.codec import decode_entry, encode_entry
from haussmann.ledger.ledger import Entry
from haussmann.llmkit.client import Response

_SCHEMA = Path(__file__).with_name("schema.sql")
_RESPONSE = TypeAdapter(Response)

type Connection = psycopg.AsyncConnection[tuple[Any, ...]]


async def connect(url: str) -> Connection:
    """Open a connection in autocommit mode and create the tables if they are missing."""
    connection = await psycopg.AsyncConnection.connect(url, autocommit=True)
    await connection.execute(cast(LiteralString, _SCHEMA.read_text()))
    return connection


class PostgresJournal:
    """One connection, used by one run at a time. The run's lock lasts as long as the connection."""

    def __init__(self, connection: Connection) -> None:
        self._db = connection

    async def open(self, run_id: str, inputs_digest: str) -> RunState:
        await self._db.execute(
            "insert into runs (id, inputs_digest) values (%s, %s) on conflict do nothing",
            (run_id, inputs_digest),
        )
        stored = await self._one("select inputs_digest from runs where id = %s", (run_id,))
        if stored != inputs_digest:
            raise InputsChanged(run_id)
        if not await self._one("select pg_try_advisory_lock(hashtextextended(%s, 0))", (run_id,)):
            raise RunLocked(run_id)
        entries = await self._all(
            "select entry from ledger_entries where run_id = %s order by tx, position", (run_id,)
        )
        steps = await self._all(
            "select key, result from steps where run_id = %s order by seq", (run_id,)
        )
        return RunState(
            run_id,
            tuple(decode_entry(row[0]) for row in entries),
            {row[0]: cast(Json, row[1]) for row in steps},
        )

    async def call(self, run_id: str, key: str) -> Response | None:
        stored = await self._one(
            "select response from calls where run_id = %s and key = %s", (run_id, key)
        )
        return None if stored is None else _RESPONSE.validate_python(stored)

    async def record_call(
        self, run_id: str, step: str, key: str, response: Response, cost_usd: Decimal
    ) -> None:
        await self._db.execute(
            "insert into calls (run_id, key, step, model, input_tokens, output_tokens, cost_usd,"
            " response) values (%s, %s, %s, %s, %s, %s, %s, %s) on conflict do nothing",
            (
                run_id,
                key,
                step,
                response.model,
                response.usage.input_tokens,
                response.usage.output_tokens,
                cost_usd,
                Jsonb(_RESPONSE.dump_python(response, mode="json")),
            ),
        )

    async def commit(self, run_id: str, step: str, entries: Sequence[Entry], result: Json) -> None:
        try:
            async with self._db.transaction():
                await self._db.execute(
                    "insert into steps (run_id, key, seq, result) select %s, %s,"
                    " coalesce(max(seq), 0) + 1, %s from steps where run_id = %s",
                    (run_id, step, Jsonb(result), run_id),
                )
                last = await self._one(
                    "select coalesce(max(tx), 0) from ledger_entries where run_id = %s", (run_id,)
                )
                if any(entry.tx <= last for entry in entries):
                    raise StepRepeated(step)
                for position, entry in enumerate(entries):
                    await self._db.execute(
                        "insert into ledger_entries (run_id, tx, position, step, entry)"
                        " values (%s, %s, %s, %s, %s)",
                        (run_id, entry.tx, position, step, Jsonb(encode_entry(entry))),
                    )
        except psycopg.errors.UniqueViolation as error:
            raise StepRepeated(step) from error

    async def spent(self, run_id: str) -> Decimal:
        total = await self._one(
            "select coalesce(sum(cost_usd), 0) from calls where run_id = %s", (run_id,)
        )
        return Decimal(total)

    async def keys(self, run_id: str, step: str) -> frozenset[str]:
        rows = await self._all(
            "select key from calls where run_id = %s and step = %s", (run_id, step)
        )
        return frozenset(row[0] for row in rows)

    async def costs(self, run_id: str) -> tuple[StepCost, ...]:
        rows = await self._all(
            "select step, response, cost_usd from calls where run_id = %s order by n", (run_id,)
        )
        return summarize([(row[0], _RESPONSE.validate_python(row[1]), row[2]) for row in rows])

    async def _one(self, query: LiteralString, parameters: tuple[object, ...]) -> Any:
        row = await (await self._db.execute(query, parameters)).fetchone()
        return None if row is None else row[0]

    async def _all(
        self, query: LiteralString, parameters: tuple[object, ...]
    ) -> list[tuple[Any, ...]]:
        return await (await self._db.execute(query, parameters)).fetchall()
