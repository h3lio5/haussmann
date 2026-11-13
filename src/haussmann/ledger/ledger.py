"""An append-only record of facts, where they came from and what was decided about them."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from haussmann.coretypes.values import FactKey, Value


@dataclass(frozen=True, slots=True)
class Citation:
    """`quote` is the passage that states the value, when the author has one."""

    doc_id: str
    locator: str | None
    quote: str = ""


class Status(StrEnum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"
    SET_ASIDE = "set_aside"


@dataclass(frozen=True, slots=True)
class Condition:
    """The case a fact is stated for: it holds when the fact `key` has the value `value`."""

    key: FactKey
    value: str


@dataclass(frozen=True, slots=True)
class NewFact:
    key: FactKey
    value: Value
    citations: tuple[Citation, ...] = ()
    method: str = "extracted"
    holds_when: Condition | None = None


@dataclass(frozen=True, slots=True)
class Assess:
    fact_id: str
    status: Status
    reason: str = ""


@dataclass(frozen=True, slots=True)
class NewConflict:
    key: FactKey
    fact_ids: tuple[str, ...]
    kind: str


@dataclass(frozen=True, slots=True)
class Resolve:
    """`chosen` is None when the conflict is escalated to a person."""

    conflict_id: str
    chosen: str | None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Ask:
    key: FactKey
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Flag:
    """A fact that needs a person's attention, with the reason."""

    fact_id: str
    reason: str


type Record = NewFact | Assess | NewConflict | Resolve | Ask | Flag


@dataclass(frozen=True, slots=True)
class Fact:
    id: str
    key: FactKey
    value: Value
    citations: tuple[Citation, ...]
    method: str
    author: str
    tx: int
    holds_when: Condition | None = None


@dataclass(frozen=True, slots=True)
class Resolution:
    chosen: str | None
    reason: str
    author: str
    tx: int


@dataclass(frozen=True, slots=True)
class Conflict:
    """`resolution` is None while the conflict is open."""

    id: str
    key: FactKey
    fact_ids: tuple[str, ...]
    kind: str
    tx: int
    resolution: Resolution | None = None


@dataclass(frozen=True, slots=True)
class Question:
    key: FactKey
    reason: str
    author: str
    tx: int


@dataclass(frozen=True, slots=True)
class Flagged:
    fact_id: str
    reason: str
    author: str
    tx: int


class LedgerError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Entry:
    """One accepted record, with the transaction it belongs to and the id it was given."""

    tx: int
    author: str
    record: Record
    assigned_id: str | None


class Ledger:
    """In memory. Every read is derived from the list of appended entries."""

    def __init__(self, entries: Sequence[Entry] = ()) -> None:
        self._entries: list[Entry] = list(entries)

    @property
    def tx(self) -> int:
        """The number of the last transaction, 0 when empty."""
        return self._entries[-1].tx if self._entries else 0

    def append(self, author: str, records: Sequence[Record]) -> int:
        """Write all the records as one transaction, or none of them."""
        if not records:
            raise LedgerError("a transaction needs at least one record")
        tx = self.tx + 1
        staged = Ledger(self._entries)
        for record in records:
            staged._add(tx, author, record)
        self._entries = staged._entries
        return tx

    @classmethod
    def load(cls, entries: Sequence[Entry]) -> "Ledger":
        """Rebuild a ledger from stored entries, applying the checks `append` applies."""
        ledger = cls()
        for entry in entries:
            if entry.tx < 1 or entry.tx not in (ledger.tx, ledger.tx + 1):
                raise LedgerError(f"transaction {entry.tx} does not follow {ledger.tx}")
            ledger._add(entry.tx, entry.author, entry.record)
            if ledger._entries[-1] != entry:
                raise LedgerError(f"stored id {entry.assigned_id} is not the id the ledger assigns")
        return ledger

    def since(self, tx: int) -> tuple[Entry, ...]:
        """The entries of every transaction after `tx`, in order."""
        return tuple(entry for entry in self._entries if entry.tx > tx)

    def at(self, tx: int) -> "Ledger":
        return Ledger([entry for entry in self._entries if entry.tx <= tx])

    def facts(self, key: FactKey | None = None) -> tuple[Fact, ...]:
        return tuple(
            Fact(
                entry.assigned_id or "",
                entry.record.key,
                entry.record.value,
                entry.record.citations,
                entry.record.method,
                entry.author,
                entry.tx,
                entry.record.holds_when,
            )
            for entry in self._entries
            if isinstance(entry.record, NewFact) and key in (None, entry.record.key)
        )

    def fact(self, fact_id: str) -> Fact:
        for fact in self.facts():
            if fact.id == fact_id:
                return fact
        raise LedgerError(f"no fact {fact_id}")

    def status(self, fact_id: str) -> Status:
        self.fact(fact_id)
        latest = Status.CANDIDATE
        for entry in self._entries:
            if isinstance(entry.record, Assess) and entry.record.fact_id == fact_id:
                latest = entry.record.status
        return latest

    def conflicts(self) -> tuple[Conflict, ...]:
        resolutions = {
            entry.record.conflict_id: Resolution(
                entry.record.chosen, entry.record.reason, entry.author, entry.tx
            )
            for entry in self._entries
            if isinstance(entry.record, Resolve)
        }
        return tuple(
            Conflict(
                entry.assigned_id or "",
                entry.record.key,
                entry.record.fact_ids,
                entry.record.kind,
                entry.tx,
                resolutions.get(entry.assigned_id or ""),
            )
            for entry in self._entries
            if isinstance(entry.record, NewConflict)
        )

    def questions(self) -> tuple[Question, ...]:
        return tuple(
            Question(entry.record.key, entry.record.reason, entry.author, entry.tx)
            for entry in self._entries
            if isinstance(entry.record, Ask)
        )

    def flags(self) -> tuple[Flagged, ...]:
        return tuple(
            Flagged(entry.record.fact_id, entry.record.reason, entry.author, entry.tx)
            for entry in self._entries
            if isinstance(entry.record, Flag)
        )

    def _count(self, kind: type) -> int:
        return sum(1 for entry in self._entries if isinstance(entry.record, kind))

    def _add(self, tx: int, author: str, record: Record) -> None:
        assigned: str | None = None
        match record:
            case NewFact():
                assigned = f"f{self._count(NewFact) + 1}"
            case Assess(fact_id) | Flag(fact_id):
                self.fact(fact_id)
            case NewConflict(key, fact_ids):
                if len(set(fact_ids)) < 2:
                    raise LedgerError("a conflict needs at least two different facts")
                for fact_id in fact_ids:
                    if self.fact(fact_id).key != key:
                        raise LedgerError(f"{fact_id} is not a fact about the conflict's key")
                assigned = f"c{self._count(NewConflict) + 1}"
            case Resolve(conflict_id, chosen):
                found = next((c for c in self.conflicts() if c.id == conflict_id), None)
                if found is None:
                    raise LedgerError(f"no conflict {conflict_id}")
                if chosen is not None and chosen not in found.fact_ids:
                    raise LedgerError(f"{chosen} is not one of the facts in {conflict_id}")
            case Ask():
                pass
        self._entries.append(Entry(tx, author, record, assigned))
