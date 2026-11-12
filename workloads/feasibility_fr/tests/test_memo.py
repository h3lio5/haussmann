import asyncio
import datetime as dt
import json
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from feasibility_fr.benchmark.memos import (
    EDITED,
    coverage,
    edit,
    fallbacks,
    run,
    summary,
    typed_digits,
)
from feasibility_fr.benchmark.run import selected
from feasibility_fr.benchmark.scenarios import SCENARIOS
from feasibility_fr.engine.memo import (
    FLAG_MARK,
    ISSUE,
    MEMO,
    NOTHING,
    OPEN,
    Bound,
    Memo,
    bind,
    render,
    write_memo,
)
from feasibility_fr.engine.rules import flag_dates
from feasibility_fr.engine.run import renderings
from feasibility_fr.engine.spec import RequiredFact
from feasibility_fr.schema import ATTRIBUTES
from haussmann.buildkit.build import Sentence
from haussmann.coretypes.values import FactKey, Quantity
from haussmann.docparse.cards import DocumentCard
from haussmann.docparse.elements import Element
from haussmann.ledger.ledger import Citation, Ledger, NewFact
from haussmann.llmkit.client import Request, Response, Usage
from haussmann.llmkit.replay import ReplayClient, ReplayStore
from haussmann.verify.settle import verify

DATA = Path(__file__).parent.parent / "benchmark_data"
AS_OF = dt.date(2026, 10, 1)
AREA = FactKey("site", "land_area")
OWNER = FactKey("site", "owner")
HEIGHT = FactKey("site", "max_height")
END = FactKey("lease:a", "lease_end")
SOIL = FactKey("site", "soil_study")
ASKED = (
    RequiredFact(AREA, "Le bien - Contenance"),
    RequiredFact(OWNER, "Le bien - Propriétaire"),
    RequiredFact(HEIGHT, "Le bien - Hauteur maximale"),
    RequiredFact(END, "Bail A - Échéance du bail"),
    RequiredFact(SOIL, "Le bien - Étude de sol"),
)
ELEMENTS = (
    Element("cadastre", "p1", "Contenance : 0,12 ha."),
    Element("notaire", "p1", "Le bien appartient à la Commune."),
    Element("plaquette", "p1", "Le bien appartient à la SCI du Parc. Hauteur : 15 m."),
    Element("reglement", "p8", "Hauteur maximale : 9 m."),
    Element("bail", "p2", "Le bail prend fin le 30 juin 2025."),
)
CARDS = (
    DocumentCard("cadastre", "cadastral_extract", dt.date(2025, 1, 1), 3),
    DocumentCard("notaire", "notary_note", dt.date(2025, 1, 1), 3),
    DocumentCard("plaquette", "sales_brochure", dt.date(2026, 1, 1), 1),
    DocumentCard("reglement", "zoning_regulation", dt.date(2025, 1, 1), 3),
    DocumentCard("bail", "lease", dt.date(2020, 1, 1), 3),
)


def ledger() -> Ledger:
    made = Ledger()
    stated = [
        (AREA, Quantity(Decimal("0.12"), "ha"), "cadastre", "p1"),
        (OWNER, "la Commune", "notaire", "p1"),
        (OWNER, "la SCI du Parc", "plaquette", "p1"),
        (HEIGHT, Quantity(Decimal(9), "m"), "reglement", "p8"),
        (END, dt.date(2025, 6, 30), "bail", "p2"),
    ]
    made.append("finder", [NewFact(k, v, (Citation(d, loc),)) for k, v, d, loc in stated])
    keys = [fact.key for fact in ASKED]
    verify(made, ELEMENTS, CARDS, ATTRIBUTES, keys, {}, renderings)
    flag_dates(made, keys, ATTRIBUTES, AS_OF)
    return made


SITE = [
    "Le terrain mesure {site.land_area}.",
    "Il appartient, selon les pièces retenues, à {site.owner}.",
]
RULES = ["La hauteur est limitée à {site.max_height}."]
LEASE = ["Le bail A prend fin le {lease:a.lease_end}."]


class Scripted:
    """Answers each section with a prepared draft and counts the calls."""

    def __init__(self, **drafts: list[list[str]]) -> None:
        self.drafts = drafts
        self.calls: list[str] = []

    async def complete(self, request: Request, *, sample: int = 0) -> Response:
        title = request.messages[1].text.splitlines()[0].removeprefix("Section : ")
        section = next(s.id for s in MEMO.sections if s.title == title)
        self.calls.append(section)
        text = json.dumps({"sentences": self.drafts[section].pop(0)})
        return Response(text, "stop", request.model, Usage(100, 20), 0.5)


def good() -> Scripted:
    return Scripted(site=[SITE, SITE], rules=[RULES], occupancy=[LEASE])


def test_every_attribute_is_stated_by_exactly_one_prose_section() -> None:
    selecting = [a for s in MEMO.sections if s.kind == "prose" for a in s.attributes]
    assert sorted(selecting) == sorted(ATTRIBUTES)


def test_ledger_facts_become_inputs_with_printed_values_flags_and_sources() -> None:
    bound = {b.input.name: b for b in bind(ledger(), ASKED, ATTRIBUTES)}
    area = bound["site.land_area"]
    assert (area.input.text, area.input.flagged) == ("1 200 m²", False)
    assert area.citations == (("cadastre", "p1"),)
    owner = bound["site.owner"]
    assert (owner.input.text, owner.input.flagged) == ("la Commune", True)
    assert owner.citations == (("notaire", "p1"), ("plaquette", "p1"))
    assert bound["lease:a.lease_end"].input.flagged


def test_a_disagreement_a_date_flag_and_a_missing_fact_each_get_their_entry() -> None:
    bound = {b.input.name: b.input for b in bind(ledger(), ASKED, ATTRIBUTES)}
    dispute = bound["site.owner#issue"]
    assert dispute.attribute == ISSUE
    assert "la Commune (notaire p1) ; la SCI du Parc (plaquette p1)" in dispute.text
    assert "valeur retenue : la Commune (source de plus forte autorité)" in dispute.text
    ended = bound["lease:a.lease_end#issue"].text
    assert ended == "Bail A - Échéance du bail : échéance dépassée à la date de revue."
    missing = bound["site.soil_study#open"]
    assert missing.attribute == OPEN and "aucun document ne l'établit" in missing.text
    assert "site.soil_study" not in bound and "site.max_height#issue" not in bound


def build(
    client: Scripted, cache: dict[str, tuple[Sentence, ...]], bound: Sequence[Bound] | None = None
) -> Memo:
    return asyncio.run(write_memo(ledger(), ASKED, ATTRIBUTES, client, "small", cache, bound=bound))


def test_the_memo_prints_values_from_inputs_and_marks_flagged_ones() -> None:
    memo = build(good(), {})
    text = render(memo, AS_OF)
    assert "## Le site et sa propriété\n\nLe terrain mesure 1 200 m²." in text
    assert f"à la Commune{FLAG_MARK}." in text
    assert f"prend fin le 30 juin 2025{FLAG_MARK}." in text
    assert "## Points à résoudre\n\n- Bail A - Échéance du bail :" in text
    assert "## Questions ouvertes\n\n- Le bien - Étude de sol : aucun document" in text
    assert f"## Prix\n\n{NOTHING}" in text
    assert typed_digits(memo) == 0 and coverage(memo) == (4, 4)
    assert memo.refusals == () and len(memo.responses) == 3


def test_a_draft_that_types_a_number_is_refused_then_replaced_by_the_plain_list() -> None:
    typed = ["Le terrain mesure 1 200 m², soit {site.land_area}, à {site.owner}."]
    client = Scripted(site=[typed, typed], rules=[RULES], occupancy=[LEASE])
    memo = build(client, {})
    assert [(r.section_id, r.draft) for r in memo.refusals] == [("site", 1), ("site", 2)]
    assert fallbacks(memo) == 1 and typed_digits(memo) == 0
    assert "Le bien - Contenance : 1 200 m²." in render(memo, AS_OF)
    assert "soit" not in render(memo, AS_OF)


def test_after_one_edited_fact_only_its_section_is_rewritten() -> None:
    client, cache = good(), dict[str, tuple[Sentence, ...]]()
    memo = build(client, cache)
    assert client.calls == ["site", "rules", "occupancy"]
    rebuilt = build(client, cache, bound=edit(memo.bound, EDITED))
    assert client.calls == ["site", "rules", "occupancy", "site"]
    assert [b.section_id for b in rebuilt.built if not b.reused] == ["site"]
    again = build(client, cache, bound=memo.bound)
    assert all(b.reused for b in again.built) and len(client.calls) == 4


def test_the_committed_memos_reproduce_from_recordings_without_a_network() -> None:
    client = ReplayClient(ReplayStore(DATA / "recordings" / "completions"))
    runs = asyncio.run(run(DATA, selected(list(SCENARIOS.values()), False), client))
    assert summary(runs) == (DATA / "results" / "memos.md").read_text(encoding="utf-8")
    for made in runs:
        committed = DATA / made.scenario_id / "memo" / "memo.md"
        assert made.text == committed.read_text(encoding="utf-8")
        assert typed_digits(made.memo) == 0


def test_a_sentence_with_no_fact_is_left_out_of_the_memo_and_counted() -> None:
    padded = [*SITE, "Ce terrain est bien situé."]
    client = Scripted(site=[padded], rules=[RULES], occupancy=[LEASE])
    memo = build(client, {})
    assert memo.dropped == ("Ce terrain est bien situé.",) and memo.refusals == ()
    assert "bien situé" not in render(memo, AS_OF)
