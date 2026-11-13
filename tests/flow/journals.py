"""The two journals, opened the same way, for tests that must pass on both."""

import os
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import pytest

from haussmann.flow.journal import Journal, MemoryJournal
from haussmann.flow.postgres import PostgresJournal, connect

type Opener = Callable[[], AbstractAsyncContextManager[Journal]]

DB_URL = os.environ.get("HAUSSMANN_DB_URL", "")


@asynccontextmanager
async def memory() -> AsyncGenerator[Journal]:
    yield MemoryJournal()


@asynccontextmanager
async def postgres() -> AsyncGenerator[Journal]:
    connection = await connect(DB_URL)
    try:
        yield PostgresJournal(connection)
    finally:
        await connection.close()


needs_db = pytest.mark.skipif(not DB_URL, reason="HAUSSMANN_DB_URL is not set")
BOTH = [
    pytest.param(memory, id="memory"),
    pytest.param(postgres, id="postgres", marks=[pytest.mark.db, needs_db]),
]
