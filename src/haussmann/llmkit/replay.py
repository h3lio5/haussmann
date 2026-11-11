"""Replay cache: return a recorded response for a request seen before."""

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from haussmann.llmkit.client import LLMClient, Request, Response

_KEY_VERSION = "v1"


def canonical_request(request: Request) -> dict[str, Any]:
    """The request as plain data, with each image replaced by the hash of its bytes."""
    body = asdict(request)
    if request.temperature is not None:
        body["temperature"] = float(request.temperature)
    for message in body["messages"]:
        message["images"] = [hashlib.sha256(image).hexdigest() for image in message["images"]]
    return body


def request_key(request: Request, sample: int) -> str:
    canonical = json.dumps(
        canonical_request(request), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(f"{_KEY_VERSION}\n{sample}\n{canonical}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Recording:
    request: dict[str, Any]
    sample: int
    response: Response


_RECORDING = TypeAdapter(Recording)


class ReplayMiss(KeyError):
    pass


class ReplayStore:
    """One JSON file per request key under `root`."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        return self._root / key[:2] / f"{key}.json"

    def get(self, key: str) -> Response | None:
        path = self._path(key)
        if not path.exists():
            return None
        return _RECORDING.validate_json(path.read_bytes()).response

    def put(self, key: str, recording: Recording) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_RECORDING.dump_json(recording, indent=2) + b"\n")


class ReplayClient:
    """Serves recordings; on a miss calls `inner` and records, or raises without one."""

    def __init__(self, store: ReplayStore, inner: LLMClient | None = None) -> None:
        self._store = store
        self._inner = inner

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        key = request_key(request, sample)
        recorded = self._store.get(key)
        if recorded is not None:
            return recorded
        if self._inner is None:
            raise ReplayMiss(f"no recording for {request.model} sample {sample}: {key}")
        response = await self._inner.complete(request, sample=sample)
        self._store.put(key, Recording(canonical_request(request), sample, response))
        return response
