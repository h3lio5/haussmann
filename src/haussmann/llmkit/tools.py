"""The tool loop: call the model, run the tools it asks for, repeat within a budget."""

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, cast

from haussmann.llmkit.client import LLMClient, Message, Request, Response, ToolCall, ToolSpec

type ToolFunction = Callable[[Mapping[str, Any]], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class Tool:
    spec: ToolSpec
    run: ToolFunction


class ToolError(Exception):
    """Raised by a tool to tell the model its call was wrong; the text is shown to the model."""


@dataclass(frozen=True, slots=True)
class Budget:
    """`max_tokens` counts input and output tokens over every call of the loop."""

    max_turns: int
    max_tokens: int


class Stop(StrEnum):
    ANSWERED = "answered"
    TURN_LIMIT = "turn_limit"
    TOKEN_LIMIT = "token_limit"
    REPEATED_CALL = "repeated_call"


@dataclass(frozen=True, slots=True)
class Step:
    call: ToolCall
    result: str
    failed: bool


@dataclass(frozen=True, slots=True)
class LoopResult:
    """`answer` is the model's final text, empty unless `stop` is ANSWERED."""

    answer: str
    stop: Stop
    messages: tuple[Message, ...]
    steps: tuple[Step, ...]
    responses: tuple[Response, ...]


async def run_tools(
    client: LLMClient,
    request: Request,
    tools: Sequence[Tool],
    budget: Budget,
    *,
    sample: int = 0,
) -> LoopResult:
    by_name = {tool.spec.name: tool for tool in tools}
    specs = tuple(tool.spec for tool in tools)
    messages = list(request.messages)
    steps: list[Step] = []
    responses: list[Response] = []
    seen: set[tuple[str, str]] = set()
    tokens = 0

    def finish(stop: Stop, answer: str = "") -> LoopResult:
        return LoopResult(answer, stop, tuple(messages), tuple(steps), tuple(responses))

    for _ in range(budget.max_turns):
        turn = replace(request, messages=tuple(messages), tools=specs)
        response = await client.complete(turn, sample=sample)
        responses.append(response)
        tokens += response.usage.input_tokens + response.usage.output_tokens
        messages.append(Message("assistant", response.text, tool_calls=response.tool_calls))
        if not response.tool_calls:
            return finish(Stop.ANSWERED, response.text)

        for call in response.tool_calls:
            if (call.name, call.arguments) in seen:
                return finish(Stop.REPEATED_CALL)
            seen.add((call.name, call.arguments))
            result, failed = await _run(by_name.get(call.name), call)
            steps.append(Step(call, result, failed))
            messages.append(Message("tool", result, tool_call_id=call.id))

        if tokens >= budget.max_tokens:
            return finish(Stop.TOKEN_LIMIT)
    return finish(Stop.TURN_LIMIT)


async def _run(tool: Tool | None, call: ToolCall) -> tuple[str, bool]:
    """The text to show the model, and whether the call failed."""
    if tool is None:
        return f"error: there is no tool named {call.name}", True
    try:
        arguments: Any = json.loads(call.arguments or "{}")
    except json.JSONDecodeError as error:
        return f"error: the arguments are not valid JSON ({error.msg})", True
    if not isinstance(arguments, dict):
        return "error: the arguments must be a JSON object", True
    try:
        return await tool.run(cast(Mapping[str, Any], arguments)), False
    except ToolError as error:
        return f"error: {error}", True
