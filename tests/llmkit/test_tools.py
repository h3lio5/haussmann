import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from haussmann.llmkit.chat_completions import parse_reply, request_body
from haussmann.llmkit.client import Message, Request, Response, ToolCall, ToolSpec, Usage
from haussmann.llmkit.replay import ReplayClient, ReplayMiss, ReplayStore, request_key
from haussmann.llmkit.tools import Budget, LoopResult, Stop, Tool, ToolError, run_tools

REQUEST = Request("model-a", (Message("system", "Find it."), Message("user", "Height?")), 500)
SEARCH = ToolSpec("search", "Search the documents.", {"type": "object"})
ROOMY = Budget(max_turns=6, max_tokens=100_000)
PINNED_KEY = "b48f84a5c1fab31f21b812817ef8c7e98100997d148bc1b4ecc79869f80ce6ff"


def reply(text: str = "", *calls: ToolCall, tokens: int = 100) -> Response:
    return Response(
        text, "tool_calls" if calls else "stop", "model-a", Usage(tokens, 10), 0.1, calls
    )


def call(call_id: str, query: str, name: str = "search") -> ToolCall:
    return ToolCall(call_id, name, json.dumps({"query": query}))


class Scripted:
    """Returns the given responses in order and remembers every request."""

    def __init__(self, *responses: Response) -> None:
        self.responses = list(responses)
        self.requests: list[Request] = []

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        self.requests.append(request)
        return self.responses.pop(0)


class Searching:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def run(self, arguments: Mapping[str, Any]) -> str:
        if "query" not in arguments:
            raise ToolError("a query is required")
        self.queries.append(arguments["query"])
        return f"result for {arguments['query']}"

    def tool(self) -> Tool:
        return Tool(SEARCH, self.run)


def loop(client: Scripted, tool: Tool, budget: Budget = ROOMY) -> LoopResult:
    return asyncio.run(run_tools(client, REQUEST, [tool], budget))


def test_an_immediate_answer_ends_the_loop_after_one_call() -> None:
    client = Scripted(reply("9 m"))
    result = loop(client, Searching().tool())
    assert (result.answer, result.stop, result.steps) == ("9 m", Stop.ANSWERED, ())
    assert len(client.requests) == 1
    assert client.requests[0].tools == (SEARCH,)


def test_tool_results_are_fed_back_in_order_and_answer_their_calls() -> None:
    search = Searching()
    client = Scripted(
        reply("", call("c1", "hauteur"), call("c2", "emprise")),
        reply("", call("c3", "recul")),
        reply("9 m, 30 %, 4 m"),
    )
    result = loop(client, search.tool())

    assert result.stop is Stop.ANSWERED and result.answer == "9 m, 30 %, 4 m"
    assert search.queries == ["hauteur", "emprise", "recul"]
    assert [(s.call.id, s.result, s.failed) for s in result.steps] == [
        ("c1", "result for hauteur", False),
        ("c2", "result for emprise", False),
        ("c3", "result for recul", False),
    ]
    second = client.requests[1].messages
    assert second[:2] == REQUEST.messages
    assert second[2].role == "assistant" and [c.id for c in second[2].tool_calls] == ["c1", "c2"]
    assert [(m.role, m.tool_call_id, m.text) for m in second[3:]] == [
        ("tool", "c1", "result for hauteur"),
        ("tool", "c2", "result for emprise"),
    ]
    assert result.messages[-1] == Message("assistant", "9 m, 30 %, 4 m")
    assert len(result.responses) == 3


def test_the_turn_limit_stops_the_loop_without_another_model_call() -> None:
    client = Scripted(*(reply("", call(f"c{n}", f"q{n}")) for n in range(5)))
    result = loop(client, Searching().tool(), Budget(max_turns=3, max_tokens=100_000))
    assert (result.stop, result.answer) == (Stop.TURN_LIMIT, "")
    assert len(client.requests) == 3 and len(result.steps) == 3


def test_the_token_limit_stops_the_loop_after_the_call_that_crossed_it() -> None:
    client = Scripted(*(reply("", call(f"c{n}", f"q{n}"), tokens=400) for n in range(5)))
    result = loop(client, Searching().tool(), Budget(max_turns=10, max_tokens=800))
    assert result.stop is Stop.TOKEN_LIMIT
    assert len(client.requests) == 2 and len(result.steps) == 2


def test_a_repeated_call_stops_the_loop_before_running_it_again() -> None:
    search = Searching()
    client = Scripted(
        reply("", call("c1", "hauteur")), reply("", call("c2", "hauteur")), reply("x")
    )
    result = loop(client, search.tool())
    assert result.stop is Stop.REPEATED_CALL
    assert search.queries == ["hauteur"]
    assert len(client.requests) == 2


def test_a_bad_call_is_reported_to_the_model_as_a_failed_step() -> None:
    client = Scripted(
        reply("", ToolCall("c1", "open_safe", "{}")),
        reply("", ToolCall("c2", "search", "{not json")),
        reply("", ToolCall("c3", "search", "[1, 2]")),
        reply("", ToolCall("c4", "search", "{}")),
        reply("gave up"),
    )
    result = loop(client, Searching().tool())
    assert result.stop is Stop.ANSWERED
    assert [step.failed for step in result.steps] == [True, True, True, True]
    assert "no tool named open_safe" in result.steps[0].result
    assert "not valid JSON" in result.steps[1].result
    assert "must be a JSON object" in result.steps[2].result
    assert result.steps[3].result == "error: a query is required"
    assert client.requests[1].messages[-1] == Message("tool", result.steps[0].result, (), (), "c1")


def test_a_bug_in_a_tool_is_not_hidden_from_the_caller() -> None:
    async def broken(arguments: Mapping[str, Any]) -> str:
        raise RuntimeError("bug")

    with pytest.raises(RuntimeError):
        loop(Scripted(reply("", call("c1", "x"))), Tool(SEARCH, broken))


def test_tool_fields_go_on_the_wire_and_come_back() -> None:
    conversation = Request(
        "model-a",
        (
            Message("user", "Height?"),
            Message("assistant", "", tool_calls=(call("c1", "hauteur"),)),
            Message("tool", "result", tool_call_id="c1"),
        ),
        100,
        tools=(SEARCH,),
    )
    body = request_body(conversation)
    assert body["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search the documents.",
                "parameters": {"type": "object"},
            },
        }
    ]
    assert body["messages"] == [
        {"role": "user", "content": "Height?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"query": "hauteur"}'},
                }
            ],
        },
        {"role": "tool", "content": "result", "tool_call_id": "c1"},
    ]
    wire = {
        "model": "model-a",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c9",
                            "type": "function",
                            "function": {"name": "search", "arguments": "{}"},
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }
    parsed = parse_reply(json.dumps(wire).encode(), 0.2)
    assert parsed.tool_calls == (ToolCall("c9", "search", "{}"),)
    assert (parsed.text, parsed.stop_reason) == ("", "tool_calls")


def test_a_request_without_tools_keeps_its_old_cache_key() -> None:
    plain = Request("model-a", (Message("user", "Hello"),), 10, temperature=0.0, seed=1)
    assert request_key(plain, 0) == PINNED_KEY
    with_tools = Request("model-a", (Message("user", "Hello"),), 10, tools=(SEARCH,))
    assert request_key(with_tools, 0) != request_key(Request("model-a", plain.messages, 10), 0)


def test_a_recorded_loop_replays_with_no_inner_client(tmp_path: Path) -> None:
    script = (reply("", call("c1", "hauteur")), reply("9 m"))
    live = Scripted(*script)
    recorded = asyncio.run(
        run_tools(ReplayClient(ReplayStore(tmp_path), live), REQUEST, [Searching().tool()], ROOMY)
    )
    replayed = asyncio.run(
        run_tools(ReplayClient(ReplayStore(tmp_path)), REQUEST, [Searching().tool()], ROOMY)
    )
    assert replayed == recorded
    assert len(list(tmp_path.rglob("*.json"))) == 2

    different = Searching()

    async def other(arguments: Mapping[str, Any]) -> str:
        return "a different result"

    with pytest.raises(ReplayMiss):
        asyncio.run(
            run_tools(ReplayClient(ReplayStore(tmp_path)), REQUEST, [Tool(SEARCH, other)], ROOMY)
        )
    assert different.queries == []
