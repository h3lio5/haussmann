"""How every system under test reads a scenario's files: the engine's own ingest step."""

from pathlib import Path

from feasibility_fr.workload import WORKLOAD
from haussmann.docparse.elements import Element, parse_folder, transcribe
from haussmann.engine.ingest import TRANSCRIPTION_MAX_TOKENS, transcriber
from haussmann.evalkit.generator import MANIFEST_NAME
from haussmann.llmkit.client import LLMClient

__all__ = ["TRANSCRIPTION_MAX_TOKENS", "read_folder", "scan_folder"]


def scan_folder(folder: Path) -> tuple[Element, ...]:
    """Every file except the manifest, without calling a model."""
    return parse_folder(folder, skip={MANIFEST_NAME})


async def read_folder(folder: Path, client: LLMClient, model: str) -> tuple[Element, ...]:
    """Elements with text; scanned pages are transcribed by one model call each."""
    return await transcribe(
        scan_folder(folder), transcriber(client, model, WORKLOAD.prompts.transcribe)
    )
