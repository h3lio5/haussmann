from haussmann.buildkit.build import Built, Sentence
from haussmann.review.state import (
    Approve,
    Comment,
    Event,
    RequestChanges,
    State,
    approved,
    comments,
    states,
    version,
)

OWNER = Sentence("The owner is {site.owner}.", ("site.owner",))
AREA = Sentence("The land measures {site.area}.", ("site.area",))
SITE = Built("site", "h1", (OWNER, AREA), False)
PRICE = Built("price", "p1", (Sentence("{site.price}", ("site.price",)),), False)
EMPTY = Built("risks", "r1", (), False)
BUILD = (SITE, PRICE, EMPTY)
V_SITE, V_PRICE = version(SITE), version(PRICE)


def test_a_built_section_is_in_review_and_an_empty_one_is_a_draft() -> None:
    assert states(BUILD, []) == {
        "site": State.IN_REVIEW,
        "price": State.IN_REVIEW,
        "risks": State.DRAFT,
    }
    assert not approved(BUILD, [])


def test_the_latest_decision_on_the_current_text_is_the_state() -> None:
    events: list[Event] = [
        Approve("site", V_SITE, "a"),
        RequestChanges("site", V_SITE, "b", "the owner is wrong"),
        Comment("site", V_SITE, "b", "see the deed"),
    ]
    assert states(BUILD, events)["site"] is State.CHANGES_REQUESTED
    assert states(BUILD, [*events, Approve("site", V_SITE, "a")])["site"] is State.APPROVED


def test_an_approval_does_not_carry_over_to_rewritten_text_and_survives_an_unchanged_rebuild() -> (
    None
):
    events: list[Event] = [Approve("site", V_SITE, "a"), Approve("price", V_PRICE, "a")]
    assert approved(BUILD, events)
    rewritten = Built("site", "h2", (OWNER, AREA), False)
    reused = Built("price", "p1", PRICE.sentences, True)
    after = states((rewritten, reused, EMPTY), events)
    assert (after["site"], after["price"]) == (State.IN_REVIEW, State.APPROVED)
    assert not approved((rewritten, reused, EMPTY), events)


def test_a_deliverable_with_nothing_in_it_is_not_approved() -> None:
    assert not approved((EMPTY,), [])


def test_a_comment_follows_the_facts_of_its_sentence_through_a_rewrite() -> None:
    on_owner = Comment("site", V_SITE, "a", "which deed?", ("site.owner",))
    on_area = Comment("site", V_SITE, "a", "surveyed?", ("site.area",))
    whole = Comment("site", V_SITE, "a", "too short", to_agent=True)
    elsewhere = Comment("price", V_PRICE, "a", "check")
    rewritten = Built("site", "h2", (Sentence("Owner: {site.owner}.", ("site.owner",)),), False)
    kept = comments(rewritten, [on_owner, on_area, whole, elsewhere, Approve("site", "other", "a")])
    assert kept == (on_owner, whole)


def test_text_replaced_on_the_same_inputs_is_another_version_and_needs_its_own_approval() -> None:
    reworded = Built("site", "h1", (Sentence("Owner: {site.owner}.", ("site.owner",)), AREA), False)
    assert version(reworded) != V_SITE
    assert states((reworded,), [Approve("site", V_SITE, "a")])["site"] is State.IN_REVIEW
    assert states((reworded,), [Approve("site", version(reworded), "a")])["site"] is State.APPROVED
