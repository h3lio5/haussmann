"""One run open for review: what the screen reads, and what a reviewer can do to it."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, cast

from haussmann.buildkit.build import Built, Sentence, fill
from haussmann.coretypes.values import ValueKind
from haussmann.docparse.cards import DocumentCard
from haussmann.docparse.elements import Element
from haussmann.engine.memo import (
    Memo,
    memo_step,
    printed,
    revise_step,
    write_memo,
)
from haussmann.engine.run import apply_edit, run_engine, settle_ledger
from haussmann.engine.workload import RequiredFact, Workload, read_value
from haussmann.evalkit.cases import Case
from haussmann.flow.journal import Json
from haussmann.flow.runner import Runner
from haussmann.ledger.ledger import Ledger
from haussmann.llmkit.client import LLMClient
from haussmann.llmkit.replay import ReplayMiss
from haussmann.review.diff import SectionDiff, diff
from haussmann.review.edits import edit
from haussmann.review.proposal import Proposal, ProposalRefused, accept
from haussmann.review.state import (
    Approve,
    Comment,
    Event,
    RequestChanges,
    approved,
    comments,
    states,
    version,
)
from haussmann.verify.settle import EXPERT, settled

EVENT = "review:"


class NotRecorded(Exception):
    """The action needs a model call that this replay-only session has no recording of."""


class Invalid(ValueError):
    """The request names something the run does not have, or a value that does not fit."""


@dataclass(slots=True)
class Session:
    """`rehearse` is set when the model client only replays: an edit is then tried on a
    copy first, so that an edit with no recording changes nothing."""

    workload: Workload
    run_id: str
    scenario_id: str
    folder: Path
    runner: Runner
    client: LLMClient
    asked: Sequence[RequiredFact]
    pages: Sequence[Element]
    cards: Sequence[DocumentCard]
    as_of: dt.date
    model: str
    rehearse: bool
    base: Memo
    cache: dict[str, tuple[Sentence, ...]] = field(default_factory=dict[str, tuple[Sentence, ...]])
    proposals: dict[str, Proposal] = field(default_factory=dict[str, Proposal])

    @classmethod
    async def open(
        cls,
        workload: Workload,
        run_id: str,
        scenario_id: str,
        folder: Path,
        runner: Runner,
        client: LLMClient,
        asked: Sequence[RequiredFact],
        pages: Sequence[Element],
        cards: Sequence[DocumentCard],
        as_of: dt.date,
        model: str,
        rehearse: bool,
    ) -> "Session":
        """Run the engine and write the memo, or load them when the run has them already."""
        await run_engine(workload, asked, pages, cards, runner, model, as_of)
        cache: dict[str, tuple[Sentence, ...]] = {}
        base = await memo_step(workload, runner, asked, model, cache)
        return cls(
            workload,
            run_id,
            scenario_id,
            folder,
            runner,
            client,
            asked,
            pages,
            cards,
            as_of,
            model,
            rehearse,
            base,
            cache,
        )

    # What reviewers did, read back from the run's journal.

    def _stored(self) -> list[dict[str, Any]]:
        return [cast("dict[str, Any]", result) for _, result in self.runner.finished(EVENT)]

    def events(self) -> list[Event]:
        found: list[Event] = []
        for stored in self._stored():
            match stored["type"]:
                case "approve":
                    found.append(Approve(stored["section"], stored["version"], stored["author"]))
                case "request_changes":
                    found.append(
                        RequestChanges(
                            stored["section"], stored["version"], stored["author"], stored["reason"]
                        )
                    )
                case "comment":
                    found.append(
                        Comment(
                            stored["section"],
                            stored["version"],
                            stored["author"],
                            stored["text"],
                            tuple(stored["uses"]),
                            stored["to_agent"],
                        )
                    )
                case _:
                    pass
        return found

    @property
    def memo(self) -> Memo:
        """The memo as written, with each accepted rewording applied to the section it was
        written for, as long as that section still has the inputs it had then."""
        built = self.base.built
        for stored in self._stored():
            if stored["type"] != "accept":
                continue
            sentences = tuple(Sentence(s["text"], tuple(s["uses"])) for s in stored["sentences"])
            proposal = Proposal(stored["section"], stored["hash"], sentences)
            try:
                built = accept(built, proposal)
            except ProposalRefused:
                continue
        return replace(self.base, built=built)

    async def _record(self, event: dict[str, Json]) -> None:
        number = len(self.runner.finished(EVENT)) + 1

        async def step(ledger: Ledger, client: LLMClient) -> Json:
            return event

        await self.runner.step(f"{EVENT}{number}", step)

    # What the screen reads.

    def _inputs(self, memo: Memo) -> dict[str, Any]:
        return {item.input.name: item.input for item in memo.bound}

    def _section(self, built: Built, memo: Memo, events: Sequence[Event]) -> dict[str, Json]:
        spec = next(
            section
            for section in self.workload.deliverable.spec.sections
            if section.id == built.section_id
        )
        inputs = self._inputs(memo)
        return {
            "id": built.section_id,
            "title": spec.title,
            "kind": spec.kind,
            "state": states([built], events)[built.section_id].value,
            "version": version(built),
            "sentences": [
                {
                    "text": fill(sentence, inputs, self.workload.deliverable.flag_mark),
                    "uses": list(sentence.uses),
                }
                for sentence in built.sentences
            ],
            "comments": [
                {"author": c.author, "text": c.text, "uses": list(c.uses), "to_agent": c.to_agent}
                for c in comments(built, events)
            ],
        }

    def view(self) -> dict[str, Json]:
        """The memo with, for each sentence, the inputs it states, and for each input its
        label, its printed value and where it is cited."""
        memo, events = self.memo, self.events()
        return {
            "run": self.run_id,
            "scenario": self.scenario_id,
            "as_of": self.as_of.isoformat(),
            "approved": approved(memo.built, events),
            "sections": [self._section(built, memo, events) for built in memo.built],
            "inputs": {
                item.input.name: {
                    "label": item.label,
                    "text": item.input.text,
                    "flagged": item.input.flagged,
                    "attribute": item.input.attribute,
                    "citations": [
                        {"doc_id": doc_id, "locator": locator} for doc_id, locator in item.citations
                    ],
                }
                for item in memo.bound
            },
        }

    def _key(self, name: str) -> RequiredFact:
        found = next(
            (fact for fact in self.asked if f"{fact.key.subject}.{fact.key.attribute}" == name),
            None,
        )
        if found is None:
            raise Invalid(f"{name} is not a fact of this run")
        return found

    def fact(self, name: str) -> dict[str, Json]:
        """Everything the ledger holds about one fact: each value found, its sources and
        standing, the disagreement if there is one, and which value the run settled on."""
        required = self._key(name)
        ledger = self.runner.ledger
        result = settled(ledger, required.key, self.workload.schema)
        return {
            "name": name,
            "label": required.text,
            "settled": printed(result.fact, self.workload) if result.fact is not None else None,
            "settled_fact": result.fact.id if result.fact is not None else None,
            "reasons": list(result.reasons),
            "in_conflict": list(result.conflict.fact_ids) if result.conflict is not None else [],
            "facts": [
                {
                    "id": fact.id,
                    "value": printed(fact, self.workload),
                    "status": ledger.status(fact.id).value,
                    "method": fact.method,
                    "author": fact.author,
                    "stated_for": fact.holds_when.value if fact.holds_when is not None else None,
                    "citations": [
                        {"doc_id": c.doc_id, "locator": c.locator, "quote": c.quote}
                        for c in fact.citations
                    ],
                }
                for fact in ledger.facts(required.key)
            ],
        }

    def source(self, doc_id: str, locator: str) -> dict[str, Json]:
        """The text of a cited place. A cell's locator gives its sheet, with the cell named."""
        page = locator.split("!")[0]
        element = next((e for e in self.pages if (e.doc_id, e.locator) == (doc_id, page)), None)
        if element is None:
            raise Invalid(f"{doc_id} has no {locator}")
        card = next((card for card in self.cards if card.doc_id == doc_id), None)
        return {
            "doc_id": doc_id,
            "locator": element.locator,
            "cell": locator if "!" in locator else None,
            "form": element.form,
            "type": card.type if card is not None else None,
            "date": card.date.isoformat() if card is not None and card.date else None,
            "text": element.text,
        }

    def file(self, doc_id: str) -> Path:
        found = next((path for path in sorted(self.folder.iterdir()) if path.stem == doc_id), None)
        if found is None:
            raise Invalid(f"there is no file for {doc_id}")
        return found

    def cases(self) -> list[Case]:
        """One regression case per fact an expert set in this run."""
        ledger = self.runner.ledger
        return [
            Case(self.scenario_id, 0, fact.key, fact.value, "set in review", fact.author)
            for fact in ledger.facts()
            if fact.method == EXPERT
        ]

    # What a reviewer can do.

    async def edit(self, name: str, value: str, unit: str, reason: str, author: str) -> list[Json]:
        """Set a fact's value, settle again, rebuild the memo; returns what changed."""
        required = self._key(name)
        attribute = self.workload.schema[required.key.attribute]
        names = self.workload.language.unit_names
        read = read_value(value, names.get(unit, unit), attribute, self.workload.language)
        if isinstance(read, str) and attribute.kind is not ValueKind.TEXT:
            raise Invalid(f'"{value}" cannot be read as a {attribute.kind.value}')
        before = self.memo
        if self.rehearse:
            trial = self.runner.ledger.at(self.runner.ledger.tx)
            edit(trial, required.key, read, reason, author, self.workload.schema)
            settle_ledger(self.workload, trial, self.asked, self.pages, self.cards, self.as_of)
            try:
                await write_memo(
                    self.workload, trial, self.asked, self.client, self.model, dict(self.cache)
                )
            except ReplayMiss as miss:
                raise NotRecorded("this edit needs a model call that has no recording") from miss
        await apply_edit(
            self.workload,
            self.runner,
            self.asked,
            self.pages,
            self.cards,
            self.as_of,
            required.key,
            read,
            reason,
            author,
        )
        self.base = await memo_step(self.workload, self.runner, self.asked, self.model, self.cache)
        after = self.memo
        changes = diff(
            before.built,
            after.built,
            self._inputs(before),
            self._inputs(after),
            self.workload.deliverable.flag_mark,
        )
        return [changed(change) for change in changes]

    def _built(self, section_id: str) -> Built:
        found = next((b for b in self.memo.built if b.section_id == section_id), None)
        if found is None:
            raise Invalid(f"the memo has no section {section_id}")
        return found

    async def approve(self, section_id: str, author: str) -> None:
        built = self._built(section_id)
        await self._record(
            {"type": "approve", "section": section_id, "version": version(built), "author": author}
        )

    async def request_changes(self, section_id: str, author: str, reason: str) -> None:
        built = self._built(section_id)
        await self._record(
            {
                "type": "request_changes",
                "section": section_id,
                "version": version(built),
                "author": author,
                "reason": reason,
            }
        )

    async def comment(
        self, section_id: str, author: str, text: str, uses: Sequence[str], to_agent: bool
    ) -> dict[str, Json] | None:
        """Record a comment. One addressed to the agent returns a proposed rewording of the
        section, checked and not yet applied, or None when no recording exists for it."""
        built = self._built(section_id)
        await self._record(
            {
                "type": "comment",
                "section": section_id,
                "version": version(built),
                "author": author,
                "text": text,
                "uses": list(uses),
                "to_agent": to_agent,
            }
        )
        if not to_agent:
            return None
        memo = self.memo
        try:
            proposal = await revise_step(
                self.workload, self.runner, memo, section_id, text, self.model
            )
        except ReplayMiss as miss:
            raise NotRecorded("this comment needs a model call that has no recording") from miss
        number = str(len(self.proposals) + 1)
        self.proposals[number] = proposal
        inputs = self._inputs(memo)
        return {
            "id": number,
            "section": section_id,
            "refused": list(proposal.refused),
            "sentences": [
                fill(sentence, inputs, self.workload.deliverable.flag_mark)
                for sentence in proposal.sentences
            ],
        }

    async def accept(self, proposal_id: str, author: str) -> None:
        """Apply a proposal that holds to the section it was written for."""
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise Invalid(f"there is no proposal {proposal_id}")
        try:
            accept(self.memo.built, proposal)
        except ProposalRefused as refused:
            raise Invalid(str(refused)) from refused
        await self._record(
            {
                "type": "accept",
                "section": proposal.section_id,
                "hash": proposal.hash,
                "author": author,
                "sentences": [{"text": s.text, "uses": list(s.uses)} for s in proposal.sentences],
            }
        )
        del self.proposals[proposal_id]


def changed(change: SectionDiff) -> Json:
    return {
        "section": change.section_id,
        "rewritten": change.rewritten,
        "values": [
            {"name": value.name, "before": value.before, "after": value.after}
            for value in change.values
        ],
        "removed": list(change.removed),
        "added": list(change.added),
    }
