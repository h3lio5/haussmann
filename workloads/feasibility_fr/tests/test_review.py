"""An expert's edit carried through the run: settle again, rebuild the memo, diff, review state."""

import asyncio
import datetime as dt
from decimal import Decimal

from feasibility_fr.engine.memo import FLAG_MARK, bind, memo_step, render
from feasibility_fr.engine.run import apply_edit, settle_ledger
from feasibility_fr.schema import ATTRIBUTES
from haussmann.buildkit.build import Sentence
from haussmann.flow.journal import Json, MemoryJournal
from haussmann.flow.runner import NO_CAP, Runner, open_run
from haussmann.ledger.ledger import Ledger, Status
from haussmann.llmkit.client import LLMClient
from haussmann.llmkit.pricing import Price
from haussmann.review.diff import SectionDiff, ValueChange, diff
from haussmann.review.state import Approve, Event, State, states
from haussmann.verify.settle import settled

from .test_memo import (
    AS_OF,
    ASKED,
    CARDS,
    ELEMENTS,
    END,
    LEASE,
    OWNER,
    RULES,
    SITE,
    Scripted,
    ledger,
)

PRICES = {"small": Price(Decimal(1), Decimal(1), "test", dt.date(2026, 1, 1))}
Cache = dict[str, tuple[Sentence, ...]]


async def seeded(client: Scripted) -> Runner:
    """A runner whose ledger is the settled test ledger, written by a first step."""
    runner = await open_run(MemoryJournal(), "run", "", client, PRICES, NO_CAP)

    async def found(target: Ledger, _: LLMClient) -> Json:
        for entry in ledger().since(0):
            if entry.tx > target.tx:
                target.append(
                    entry.author, [e.record for e in ledger().since(0) if e.tx == entry.tx]
                )
        return None

    await runner.step("found", found)
    return runner


def test_an_edit_rewrites_only_the_section_that_states_the_fact_and_the_diff_names_it() -> None:
    async def scenario() -> None:
        client = Scripted(site=[SITE, SITE], rules=[RULES], occupancy=[LEASE])
        runner, cache = await seeded(client), Cache()
        before = await memo_step(runner, ASKED, ATTRIBUTES, "small", cache)
        assert client.calls == ["site", "rules", "occupancy"]
        assert f"à la Commune{FLAG_MARK}." in render(before, AS_OF)

        made = await apply_edit(
            runner,
            ASKED,
            ELEMENTS,
            CARDS,
            ATTRIBUTES,
            AS_OF,
            OWNER,
            "la Ville",
            "acte du 3 mai",
            "expert:a",
        )
        after = await memo_step(runner, ASKED, ATTRIBUTES, "small", cache)

        assert client.calls == ["site", "rules", "occupancy", "site"]
        assert [b.section_id for b in after.built if not b.reused] == ["site", "issues"]
        result = settled(runner.ledger, OWNER, ATTRIBUTES)
        assert result.fact is not None and (result.fact.id, result.fact.value) == (made, "la Ville")
        overruled = [f for f in runner.ledger.facts(OWNER) if f.id != made]
        assert all(runner.ledger.status(f.id) is Status.VERIFIED for f in overruled)

        text = render(after, AS_OF)
        assert "à la Ville." in text and "la Commune" not in text
        changes = diff(
            before.built,
            after.built,
            {i.input.name: i.input for i in before.bound},
            {i.input.name: i.input for i in after.bound},
            FLAG_MARK,
        )
        site, issues = changes
        assert site == SectionDiff(
            "site",
            True,
            (ValueChange("site.owner", f"la Commune{FLAG_MARK}", "la Ville"),),
            (f"Il appartient, selon les pièces retenues, à la Commune{FLAG_MARK}.",),
            ("Il appartient, selon les pièces retenues, à la Ville.",),
        )
        assert issues.section_id == "issues" and len(issues.removed) == 1 and issues.added == ()
        assert "Propriétaire" in issues.removed[0]

    asyncio.run(scenario())


def test_an_approval_is_lost_only_by_the_sections_the_edit_rewrites() -> None:
    async def scenario() -> None:
        client = Scripted(site=[SITE, SITE], rules=[RULES], occupancy=[LEASE])
        runner, cache = await seeded(client), Cache()
        before = await memo_step(runner, ASKED, ATTRIBUTES, "small", cache)
        events: list[Event] = [Approve(b.section_id, b.hash, "expert:a") for b in before.built]
        assert set(states(before.built, events).values()) <= {State.APPROVED, State.DRAFT}

        await apply_edit(
            runner, ASKED, ELEMENTS, CARDS, ATTRIBUTES, AS_OF, OWNER, "la Ville", "acte", "expert:a"
        )
        after = await memo_step(runner, ASKED, ATTRIBUTES, "small", cache)
        now = states(after.built, events)
        assert (now["site"], now["issues"]) == (State.IN_REVIEW, State.IN_REVIEW)
        assert (now["rules"], now["occupancy"]) == (State.APPROVED, State.APPROVED)

    asyncio.run(scenario())


def test_a_date_set_by_an_expert_is_still_checked_by_the_date_rules() -> None:
    async def scenario() -> None:
        runner = await seeded(Scripted())
        await apply_edit(
            runner,
            ASKED,
            ELEMENTS,
            CARDS,
            ATTRIBUTES,
            AS_OF,
            END,
            dt.date(2026, 3, 31),
            "avenant",
            "expert:a",
        )
        bound = {item.input.name: item.input for item in bind(runner.ledger, ASKED, ATTRIBUTES)}
        assert bound["lease:a.lease_end"].flagged and "lease:a.lease_end#issue" in bound
        assert "les documents donnent" not in bound["lease:a.lease_end#issue"].text

        await apply_edit(
            runner,
            ASKED,
            ELEMENTS,
            CARDS,
            ATTRIBUTES,
            AS_OF,
            END,
            dt.date(2030, 3, 31),
            "avenant 2",
            "expert:a",
        )
        bound = {item.input.name: item.input for item in bind(runner.ledger, ASKED, ATTRIBUTES)}
        assert not bound["lease:a.lease_end"].flagged and "lease:a.lease_end#issue" not in bound

    asyncio.run(scenario())


def test_settling_a_finished_run_again_adds_nothing() -> None:
    made = ledger()
    before = made.tx
    settle_ledger(made, ASKED, ELEMENTS, CARDS, ATTRIBUTES, AS_OF)
    assert made.tx == before
