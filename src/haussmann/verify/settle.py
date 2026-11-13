"""Verify candidate facts, compute declared totals, and settle disagreements by rule."""

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from haussmann.coretypes.values import FactKey, Quantity, Schema, Value, normalize, within_tolerance
from haussmann.docparse.cards import DocumentCard
from haussmann.docparse.elements import Element
from haussmann.ledger.ledger import (
    Assess,
    Citation,
    Conflict,
    Fact,
    Ledger,
    NewConflict,
    NewFact,
    Resolve,
    Status,
)
from haussmann.verify.citations import Renderings, canonical, check_fact

AUTHOR = "verifier"
COMPUTED = "computed"
EXPERT = "expert"


def assess_candidates(
    ledger: Ledger, elements: Sequence[Element], schema: Schema, renderings: Renderings
) -> None:
    """Give every candidate fact a status: verified, or unverified with the reason."""
    records: list[Assess] = []
    for fact in ledger.facts():
        if ledger.status(fact.id) is not Status.CANDIDATE:
            continue
        attribute = schema.get(fact.key.attribute)
        if attribute is None or normalize(fact.value, attribute) is None:
            reason = "the value does not fit the attribute's kind or units"
        else:
            reason = check_fact(fact, elements, renderings)
        status = Status.VERIFIED if reason is None else Status.UNVERIFIED
        records.append(Assess(fact.id, status, reason or "stated at its cited source"))
    if records:
        ledger.append(AUTHOR, records)


def verified(ledger: Ledger, key: FactKey) -> list[Fact]:
    return [f for f in ledger.facts(key) if ledger.status(f.id) is Status.VERIFIED]


def _canonical(fact: Fact, schema: Schema) -> Value:
    value = normalize(fact.value, schema[fact.key.attribute])
    assert value is not None
    return value


def groups(facts: Sequence[Fact], schema: Schema) -> list[list[Fact]]:
    """Facts that state the same value, within the attribute's tolerance, grouped together."""
    grouped: list[list[Fact]] = []
    for fact in facts:
        tolerance = schema[fact.key.attribute].tolerance
        value = _canonical(fact, schema)
        for group in grouped:
            if within_tolerance(value, _canonical(group[0], schema), tolerance):
                group.append(fact)
                break
        else:
            grouped.append([fact])
    return grouped


@dataclass(frozen=True, slots=True)
class Standing:
    """How much a fact counts: an expert's fact first, then computed, authority, date.

    `expert` is the fact's transaction number when an expert wrote it and 0 otherwise, so
    the later of two expert facts counts more.
    """

    expert: int
    computed: bool
    authority: int
    date: dt.date


def standing(fact: Fact, cards: Mapping[str, DocumentCard]) -> Standing:
    cited = [cards[c.doc_id] for c in fact.citations if c.doc_id in cards]
    authority = max((card.authority for card in cited), default=0)
    dates = [card.date for card in cited if card.date is not None]
    expert = fact.tx if fact.method == EXPERT else 0
    return Standing(expert, fact.method == COMPUTED, authority, max(dates, default=dt.date.min))


def _rank(position: Standing) -> tuple[int, bool, int, dt.date]:
    return (position.expert, position.computed, position.authority, position.date)


def settle(ledger: Ledger, key: FactKey, schema: Schema, cards: Mapping[str, DocumentCard]) -> None:
    """Record a conflict when verified facts disagree on a key, and resolve it if a rule can."""
    distinct = groups(verified(ledger, key), schema)
    if len(distinct) < 2:
        return
    leaders = [max(group, key=lambda f: _rank(standing(f, cards))) for group in distinct]
    ranked = sorted(leaders, key=lambda f: _rank(standing(f, cards)), reverse=True)
    best, runner_up = standing(ranked[0], cards), standing(ranked[1], cards)
    chosen: str | None = ranked[0].id
    if _rank(best) == _rank(runner_up):
        chosen, reason = None, "sources of equal standing disagree"
    elif best.expert:
        reason = "set by an expert"
    elif best.computed:
        reason = "recomputed from its parts"
    elif best.authority != runner_up.authority:
        reason = "higher-authority source"
    else:
        reason = "later source"
    sides = tuple(f.id for f in leaders)
    last = next((c for c in reversed(ledger.conflicts()) if c.key == key), None)
    if (
        last is not None
        and last.resolution is not None
        and (last.fact_ids, last.resolution.chosen, last.resolution.reason)
        == (sides, chosen, reason)
    ):
        return
    ledger.append(AUTHOR, [NewConflict(key, sides, "values differ")])
    ledger.append(AUTHOR, [Resolve(ledger.conflicts()[-1].id, chosen, reason)])


@dataclass(frozen=True, slots=True)
class Settled:
    """What the ledger says about one key once verification is done.

    `fact` is None when nothing verified states the key or the disagreement was escalated.
    `supporting` holds every verified fact about the key, on either side of a disagreement.
    `set_aside` holds the facts stated for a case that is not the settled one.
    """

    key: FactKey
    fact: Fact | None
    supporting: tuple[Fact, ...]
    conflict: Conflict | None
    reasons: tuple[str, ...]
    set_aside: tuple[Fact, ...] = ()


def settled(ledger: Ledger, key: FactKey, schema: Schema) -> Settled:
    facts = verified(ledger, key)
    other = tuple(f for f in ledger.facts(key) if ledger.status(f.id) is Status.SET_ASIDE)
    conflict = next((c for c in reversed(ledger.conflicts()) if c.key == key), None)
    reasons = list(
        dict.fromkeys(
            flag.reason for flag in ledger.flags() if any(flag.fact_id == f.id for f in facts)
        )
    )
    if conflict is not None:
        chosen = conflict.resolution.chosen if conflict.resolution is not None else None
        why = conflict.resolution.reason if conflict.resolution is not None else conflict.kind
        fact = ledger.fact(chosen) if chosen is not None else None
        if fact is not None and fact.method == EXPERT:
            reasons = [flag.reason for flag in ledger.flags() if flag.fact_id == fact.id]
        return Settled(key, fact, tuple(facts), conflict, (why, *reasons), other)
    distinct = groups(facts, schema)
    fact = distinct[0][0] if distinct else None
    return Settled(key, fact, tuple(facts), None, tuple(reasons), other)


def same_case(stated: str, decided: str) -> bool:
    """Is a condition written for the decided case: the same words, or containing them whole?"""
    return f" {canonical(decided)} " in f" {canonical(stated)} "


def set_aside(ledger: Ledger, key: FactKey, schema: Schema) -> None:
    """Keep the facts of a key stated for the settled case and set the others aside.

    A fact without a condition is kept. So is every fact whose deciding key has no settled
    text value: an undecided case removes nothing. A fact set aside earlier is restored when
    the case it is stated for becomes the settled one.
    """
    records: list[Assess] = []
    for fact in ledger.facts(key):
        condition = fact.holds_when
        status = ledger.status(fact.id)
        if condition is None or status not in (Status.VERIFIED, Status.SET_ASIDE):
            continue
        decided = settled(ledger, condition.key, schema).fact
        if decided is None or not isinstance(decided.value, str) or not canonical(decided.value):
            continue
        about = f"{condition.key.subject}/{condition.key.attribute}"
        applies = same_case(condition.value, decided.value)
        if not applies and status is Status.VERIFIED:
            reason = f"stated for {condition.value}; {about} is {decided.value}"
            records.append(Assess(fact.id, Status.SET_ASIDE, reason))
        elif applies and status is Status.SET_ASIDE:
            reason = f"stated for {condition.value}; {about} is now {decided.value}"
            records.append(Assess(fact.id, Status.VERIFIED, reason))
    if records:
        ledger.append(AUTHOR, records)


def compute_total(ledger: Ledger, total: FactKey, parts: Sequence[FactKey], schema: Schema) -> None:
    """Add the sum of the settled parts as a computed, verified fact for the total.

    Nothing is added unless every part is settled as a quantity in the total's unit, or
    when the same sum is already there. An earlier sum that no longer holds is rejected.
    """
    unit = schema[total.attribute].canonical_unit
    amounts: list[Quantity] = []
    sources: list[Citation] = []
    for part in parts:
        fact = settled(ledger, part, schema).fact
        value = _canonical(fact, schema) if fact is not None else None
        if fact is None or not isinstance(value, Quantity) or value.unit != unit:
            return
        amounts.append(value)
        sources.extend(Citation(c.doc_id, None) for c in fact.citations)
    if not amounts or unit is None:
        return
    value = Quantity(sum((a.amount for a in amounts), amounts[0].amount * 0), unit)
    citations = tuple(dict.fromkeys(sources))
    earlier = [fact for fact in verified(ledger, total) if fact.method == COMPUTED]
    if earlier and (earlier[-1].value, earlier[-1].citations) == (value, citations):
        return
    if earlier:
        replaced = "recomputed after a change to its parts"
        ledger.append(AUTHOR, [Assess(fact.id, Status.REJECTED, replaced) for fact in earlier])
    ledger.append(AUTHOR, [NewFact(total, value, citations, COMPUTED)])
    computed = ledger.facts(total)[-1]
    ledger.append(AUTHOR, [Assess(computed.id, Status.VERIFIED, "sum of its settled parts")])


def verify(
    ledger: Ledger,
    elements: Sequence[Element],
    cards: Sequence[DocumentCard],
    schema: Schema,
    keys: Sequence[FactKey],
    totals: Mapping[FactKey, Sequence[FactKey]],
    renderings: Renderings,
    depends_on: Mapping[FactKey, FactKey] | None = None,
) -> None:
    """Check sources, settle each key, then compute and settle each declared total.

    `depends_on` maps a key to the key that decides which of its facts apply. Deciding keys
    are settled first; a deciding key may not itself depend on another.
    """
    dependent = depends_on or {}
    chained = [key for key, deciding in dependent.items() if deciding in dependent]
    if chained:
        raise ValueError(f"{chained[0].subject}/{chained[0].attribute} depends on a dependent key")
    by_document = {card.doc_id: card for card in cards}
    assess_candidates(ledger, elements, schema, renderings)
    for key in sorted(keys, key=lambda k: k in dependent):
        if key in totals:
            continue
        if key in dependent:
            set_aside(ledger, key, schema)
        settle(ledger, key, schema, by_document)
    for total, parts in totals.items():
        compute_total(ledger, total, parts, schema)
        settle(ledger, total, schema, by_document)
