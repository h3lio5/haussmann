import pytest

from haussmann.buildkit.build import Built, Sentence
from haussmann.buildkit.targets import Input
from haussmann.review.proposal import ProposalRefused, accept, checked
from haussmann.review.state import Approve, State, states, version

OWNER = Input("site.owner", "owner", "Town", "d1")
AREA = Input("site.area", "area", "1 200 m²", "d2")
SITE = Built(
    "site",
    "h1",
    (
        Sentence("The owner is {site.owner}.", ("site.owner",)),
        Sentence("The land measures {site.area}.", ("site.area",)),
    ),
    False,
)
PRICE = Built("price", "p1", (), False)
BETTER = ["The land, of {site.area}, belongs to {site.owner}."]


def test_a_rewrite_that_states_every_fact_through_its_placeholder_is_a_proposal() -> None:
    proposal = checked(SITE, [*BETTER, "  ", "This is a fine site."], [OWNER, AREA])
    assert proposal.refused == ()
    assert proposal.sentences == (Sentence(BETTER[0], ("site.area", "site.owner")),)
    assert (proposal.section_id, proposal.hash) == ("site", "h1")


@pytest.mark.parametrize(
    ("drafted", "reason"),
    [
        (["The land measures 1 200 m² and belongs to {site.owner}."], "contains a number"),
        (["It belongs to {site.owner}."], "{site.area} is not used"),
        (["{site.owner} holds {site.area} in zone {site.zone}."], "{site.zone} is not one"),
        (["The owner is {site.owner}.", "The land measures {site.area}."], "already has"),
        (["A fine site."], "is not used"),
    ],
)
def test_a_rewrite_that_breaks_a_rule_is_refused_with_the_reason(
    drafted: list[str], reason: str
) -> None:
    proposal = checked(SITE, drafted, [OWNER, AREA])
    assert proposal.sentences == () and any(reason in found for found in proposal.refused)
    with pytest.raises(ProposalRefused):
        accept((SITE, PRICE), proposal)


def test_accepting_replaces_the_text_of_that_section_only_and_ends_its_approval() -> None:
    proposal = checked(SITE, BETTER, [OWNER, AREA])
    site, price = accept((SITE, PRICE), proposal)
    assert site.sentences == proposal.sentences and site.hash == "h1" and price is PRICE
    approved_before = [Approve("site", version(SITE), "a")]
    assert states((SITE,), approved_before)["site"] is State.APPROVED
    assert states((site,), approved_before)["site"] is State.IN_REVIEW


def test_a_proposal_written_for_inputs_that_have_since_changed_is_not_applied() -> None:
    proposal = checked(SITE, BETTER, [OWNER, AREA])
    rebuilt = Built("site", "h2", SITE.sentences, False)
    with pytest.raises(ProposalRefused, match="has changed"):
        accept((rebuilt, PRICE), proposal)
    with pytest.raises(ProposalRefused, match="has changed"):
        accept((PRICE,), proposal)
