"""The HTTP API of the review screen. Each route is a thin call into a `Session`."""

from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from feasibility_fr.app.session import Invalid, NotRecorded, Session
from haussmann.evalkit.cases import Case, dump_cases
from haussmann.flow.journal import Json


class EditBody(BaseModel):
    name: str
    value: str
    unit: str = ""
    reason: str
    author: str


class ApproveBody(BaseModel):
    author: str


class ChangesBody(BaseModel):
    author: str
    reason: str


class CommentBody(BaseModel):
    author: str
    text: str
    uses: list[str] = []
    to_agent: bool = False


async def _answer[T](action: Callable[[], Awaitable[T]]) -> T:
    """Run an action and turn what a session refuses into the matching HTTP status."""
    try:
        return await action()
    except Invalid as invalid:
        raise HTTPException(422, str(invalid)) from invalid
    except NotRecorded as missing:
        raise HTTPException(409, str(missing)) from missing
    except ValueError as refused:
        raise HTTPException(422, str(refused)) from refused


def create_app(sessions: Mapping[str, Session], held: Callable[[], list[Case]]) -> FastAPI:
    """`sessions` maps a run id to its open session; `held` gives the committed cases."""
    app = FastAPI(title="Haussmann review")

    def session(run_id: str) -> Session:
        found = sessions.get(run_id)
        if found is None:
            raise HTTPException(404, f"there is no run {run_id}")
        return found

    def read[T](action: Callable[[], T]) -> T:
        try:
            return action()
        except Invalid as invalid:
            raise HTTPException(404, str(invalid)) from invalid

    @app.get("/api/runs")
    async def runs() -> list[dict[str, Json]]:  # pyright: ignore[reportUnusedFunction]
        return [
            {"run": run_id, "scenario": found.scenario_id, "as_of": found.as_of.isoformat()}
            for run_id, found in sessions.items()
        ]

    @app.get("/api/runs/{run_id}/memo")
    async def memo(run_id: str) -> dict[str, Json]:  # pyright: ignore[reportUnusedFunction]
        return session(run_id).view()

    @app.get("/api/runs/{run_id}/facts/{name}")
    async def fact(run_id: str, name: str) -> dict[str, Json]:  # pyright: ignore[reportUnusedFunction]
        found = session(run_id)
        return read(lambda: found.fact(name))

    @app.get("/api/runs/{run_id}/sources/{doc_id}/{locator}")
    async def source(run_id: str, doc_id: str, locator: str) -> dict[str, Json]:  # pyright: ignore[reportUnusedFunction]
        found = session(run_id)
        return read(lambda: found.source(doc_id, locator))

    @app.get("/api/runs/{run_id}/files/{doc_id}")
    async def file(run_id: str, doc_id: str) -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        found = session(run_id)
        return FileResponse(read(lambda: found.file(doc_id)))

    @app.post("/api/runs/{run_id}/edits")
    async def edit(run_id: str, body: EditBody) -> dict[str, Json]:  # pyright: ignore[reportUnusedFunction]
        found = session(run_id)
        changes = await _answer(
            lambda: found.edit(body.name, body.value, body.unit, body.reason, body.author)
        )
        return {"changes": changes, "memo": found.view()}

    @app.post("/api/runs/{run_id}/sections/{section_id}/approve")
    async def approve(run_id: str, section_id: str, body: ApproveBody) -> dict[str, Json]:  # pyright: ignore[reportUnusedFunction]
        found = session(run_id)
        await _answer(lambda: found.approve(section_id, body.author))
        return found.view()

    @app.post("/api/runs/{run_id}/sections/{section_id}/request-changes")
    async def request_changes(  # pyright: ignore[reportUnusedFunction]
        run_id: str, section_id: str, body: ChangesBody
    ) -> dict[str, Json]:
        found = session(run_id)
        await _answer(lambda: found.request_changes(section_id, body.author, body.reason))
        return found.view()

    @app.post("/api/runs/{run_id}/sections/{section_id}/comments")
    async def comment(  # pyright: ignore[reportUnusedFunction]
        run_id: str, section_id: str, body: CommentBody
    ) -> dict[str, Json]:
        found = session(run_id)
        proposal = await _answer(
            lambda: found.comment(section_id, body.author, body.text, body.uses, body.to_agent)
        )
        return {"proposal": proposal, "memo": found.view()}

    @app.post("/api/runs/{run_id}/proposals/{proposal_id}/accept")
    async def accept(run_id: str, proposal_id: str, body: ApproveBody) -> dict[str, Json]:  # pyright: ignore[reportUnusedFunction]
        found = session(run_id)
        await _answer(lambda: found.accept(proposal_id, body.author))
        return found.view()

    @app.get("/api/cases")
    async def cases() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        made = [case for found in sessions.values() for case in found.cases()]
        return {"committed": dump_cases(held()), "from_review": dump_cases(made)}

    return app
