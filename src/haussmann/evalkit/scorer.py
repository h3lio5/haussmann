"""Score a submission against a manifest. Pure: no model, no I/O."""

import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from haussmann.evalkit.groundtruth import (
    AttributeDef,
    FactKey,
    GoldFact,
    Manifest,
    Schema,
    Statement,
    StatementKind,
    Trap,
    TrapType,
    Value,
    normalize,
    within_tolerance,
)


@dataclass(frozen=True, slots=True)
class Citation:
    doc_id: str
    locator: str | None = None


@dataclass(frozen=True, slots=True)
class ReportedFact:
    key: FactKey
    value: Value
    citations: tuple[Citation, ...] = ()
    flagged: bool = False


@dataclass(frozen=True, slots=True)
class Submission:
    facts: tuple[ReportedFact, ...]
    open_questions: tuple[FactKey, ...] = ()
    memo_text: str = ""


class InvalidSubmission(ValueError):
    pass


class Outcome(StrEnum):
    CORRECT = "correct"
    BAIT = "bait"
    INVENTED = "invented"
    ABSTAINED = "abstained"
    OMITTED = "omitted"
    UNASKED = "unasked"


_REPORTED = (Outcome.CORRECT, Outcome.BAIT, Outcome.INVENTED)


@dataclass(frozen=True, slots=True)
class FactResult:
    key: FactKey
    outcome: Outcome
    answerable: bool
    well_cited: bool


@dataclass(frozen=True, slots=True)
class TrapResult:
    type: TrapType
    key: FactKey
    passed: bool


@dataclass(frozen=True, slots=True)
class Rate:
    count: int
    total: int

    @property
    def value(self) -> float | None:
        return self.count / self.total if self.total else None


@dataclass(frozen=True, slots=True)
class Score:
    facts: tuple[FactResult, ...]
    traps: tuple[TrapResult, ...]

    def _count(self, outcome: Outcome) -> int:
        return sum(1 for fact in self.facts if fact.outcome is outcome)

    @property
    def _reported(self) -> int:
        return sum(1 for fact in self.facts if fact.outcome in _REPORTED)

    @property
    def recall(self) -> Rate:
        return Rate(self._count(Outcome.CORRECT), sum(1 for f in self.facts if f.answerable))

    @property
    def precision(self) -> Rate:
        return Rate(self._count(Outcome.CORRECT), self._reported)

    @property
    def bait_rate(self) -> Rate:
        return Rate(self._count(Outcome.BAIT), self._reported)

    @property
    def invented_rate(self) -> Rate:
        return Rate(self._count(Outcome.INVENTED), self._reported)

    @property
    def abstention(self) -> Rate:
        asked = [f for f in self.facts if not f.answerable and f.outcome is not Outcome.UNASKED]
        return Rate(sum(1 for f in asked if f.outcome is Outcome.ABSTAINED), len(asked))

    @property
    def citation_correctness(self) -> Rate:
        return Rate(sum(1 for f in self.facts if f.well_cited), self._count(Outcome.CORRECT))

    @property
    def traps_passed(self) -> dict[TrapType, Rate]:
        return {
            kind: Rate(
                sum(1 for t in self.traps if t.type is kind and t.passed),
                sum(1 for t in self.traps if t.type is kind),
            )
            for kind in sorted({t.type for t in self.traps})
        }


def score(manifest: Manifest, schema: Schema, submission: Submission) -> Score:
    reported = {fact.key: fact for fact in submission.facts}
    if len(reported) != len(submission.facts):
        raise InvalidSubmission("a key is reported more than once")
    open_keys = set(submission.open_questions)
    stated: dict[FactKey, list[Statement]] = {gold.key: [] for gold in manifest.gold}
    for file in manifest.files:
        for statement in file.statements:
            stated[statement.key].append(statement)

    results: dict[FactKey, FactResult] = {}
    for gold in manifest.gold:
        fact = reported.get(gold.key)
        if fact is None:
            outcome = Outcome.ABSTAINED if gold.key in open_keys else Outcome.OMITTED
        else:
            outcome = _classify(fact.value, gold, stated[gold.key], schema[gold.key.attribute])
        well_cited = (
            fact is not None and outcome is Outcome.CORRECT and _well_cited(fact, stated[gold.key])
        )
        results[gold.key] = FactResult(gold.key, outcome, gold.value is not None, well_cited)

    unasked = sorted(
        (key for key in reported if key not in results), key=lambda k: (k.subject, k.attribute)
    )
    traps = tuple(
        TrapResult(
            trap.type,
            trap.key,
            _passes(trap, results[trap.key].outcome, reported.get(trap.key), stated[trap.key]),
        )
        for trap in manifest.traps
    )
    return Score(
        facts=(
            *results.values(),
            *(FactResult(key, Outcome.UNASKED, False, False) for key in unasked),
        ),
        traps=traps,
    )


def _canonical_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    kept = "".join(
        char
        for char in decomposed
        if not unicodedata.combining(char) and (char.isalnum() or char.isspace())
    )
    return " ".join(kept.casefold().split())


def _same(left: Value, right: Value, tolerance: Decimal) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        return _canonical_text(left) == _canonical_text(right)
    return within_tolerance(left, right, tolerance)


def _classify(
    reported: Value, gold: GoldFact, stated: list[Statement], attribute: AttributeDef
) -> Outcome:
    value = normalize(reported, attribute)
    if value is None:
        return Outcome.INVENTED
    if gold.value is not None and _same(value, gold.value, attribute.tolerance):
        return Outcome.CORRECT
    for statement in stated:
        bait = normalize(statement.value, attribute)
        if (
            statement.kind is not StatementKind.SUPPORTS
            and bait is not None
            and _same(value, bait, attribute.tolerance)
        ):
            return Outcome.BAIT
    return Outcome.INVENTED


def _cites(citation: Citation, statement: Statement) -> bool:
    return citation.doc_id == statement.doc_id and citation.locator in (None, statement.locator)


def _well_cited(fact: ReportedFact, stated: list[Statement]) -> bool:
    if not fact.citations:
        return False
    if not all(any(_cites(c, s) for s in stated) for c in fact.citations):
        return False
    supporting = [s for s in stated if s.kind is StatementKind.SUPPORTS]
    return not supporting or any(_cites(c, s) for c in fact.citations for s in supporting)


def _passes(
    trap: Trap, outcome: Outcome, fact: ReportedFact | None, stated: list[Statement]
) -> bool:
    if trap.type is TrapType.MISSING:
        return outcome is Outcome.ABSTAINED
    if fact is None:
        return False
    if trap.type is TrapType.DATE_LOGIC:
        return fact.flagged
    if outcome is not Outcome.CORRECT:
        return False

    cited = {citation.doc_id for citation in fact.citations}
    backing = [s for s in stated if s.kind is StatementKind.SUPPORTS and s.doc_id in trap.docs]
    match trap.type:
        case TrapType.UNIT:
            return True
        case TrapType.ARITHMETIC:
            return fact.flagged
        case TrapType.CONTRADICTION:
            return fact.flagged and cited.issuperset(trap.docs)
        case TrapType.DISTRACTOR:
            return cited.isdisjoint(trap.docs)
        case TrapType.SUPERSEDED:
            return any(_cites(c, s) for c in fact.citations for s in backing)
        case TrapType.BURIED:
            return any(
                c.locator is not None and _cites(c, s) for c in fact.citations for s in backing
            )
