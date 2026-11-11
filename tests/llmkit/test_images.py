import asyncio
import base64
import json
from dataclasses import replace
from pathlib import Path

from haussmann.llmkit.chat_completions import request_body
from haussmann.llmkit.client import Message, Request, Response, Usage
from haussmann.llmkit.replay import ReplayClient, ReplayStore, request_key

PNG = b"\x89PNG\r\n\x1a\n" + b"pixels"
JPEG = b"\xff\xd8\xff\xe0" + b"pixels"
REQUEST = Request("model-a", (Message("user", "Read this.", images=(PNG, JPEG)),), 100)


def test_images_are_sent_as_data_urls_with_their_media_type() -> None:
    (message,) = request_body(REQUEST)["messages"]  # type: ignore[misc]
    assert message["content"] == [
        {"type": "text", "text": "Read this."},
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64," + base64.b64encode(PNG).decode()},
        },
        {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()},
        },
    ]


def test_a_message_without_images_keeps_plain_text_content() -> None:
    body = request_body(Request("model-a", (Message("user", "Hello"),), 10))
    assert body["messages"] == [{"role": "user", "content": "Hello"}]


def test_key_changes_with_one_byte_of_an_image() -> None:
    changed = replace(REQUEST, messages=(Message("user", "Read this.", images=(PNG + b"!", JPEG)),))
    assert request_key(changed, 0) != request_key(REQUEST, 0)
    assert request_key(replace(REQUEST), 0) == request_key(REQUEST, 0)


def test_a_recording_stores_image_hashes_not_image_bytes(tmp_path: Path) -> None:
    class Live:
        async def complete(self, request: Request, *, sample: int = 0) -> Response:
            return Response("text", "stop", "model-a", Usage(1, 1), 0.1)

    asyncio.run(ReplayClient(ReplayStore(tmp_path), Live()).complete(REQUEST))
    (recording,) = tmp_path.rglob("*.json")
    stored = json.loads(recording.read_text())
    images = stored["request"]["messages"][0]["images"]
    assert all(len(image) == 64 for image in images)
    assert "pixels" not in recording.read_text()
    replayed = asyncio.run(ReplayClient(ReplayStore(tmp_path)).complete(REQUEST))
    assert replayed.text == "text"
