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
)

OWNER = Sentence("The owner is {site.owner}.", ("site.owner",))
AREA = Sentence("The land measures {site.area}.", ("site.area",))
SITE = Built("site", "h1", (OWNER, AREA), False)
PRICE = Built("price", "p1", (Sentence("{site.price}", ("site.price",)),), False)
EMPTY = Built("risks", "r1", (), False)
BUILD = (SITE, PRICE, EMPTY)


def test_a_built_section_is_in_review_and_an_empty_one_is_a_draft() -> None:
    assert states(BUILD, []) == {
        "site": State.IN_REVIEW,
        "price": State.IN_REVIEW,
        "risks": State.DRAFT,
    }
    assert not approved(BUILD, [])


def test_the_latest_decision_on_the_current_text_is_the_state() -> None:
    events: list[Event] = [
        Approve("site", "h1", "a"),
        RequestChanges("site", "h1", "b", "the owner is wrong"),
        Comment("site", "h1", "b", "see the deed"),
    ]
    assert states(BUILD, events)["site"] is State.CHANGES_REQUESTED
    assert states(BUILD, [*events, Approve("site", "h1", "a")])["site"] is State.APPROVED


def test_an_approval_does_not_carry_over_to_rewritten_text_and_survives_an_unchanged_rebuild() -> (
    None
):
    events: list[Event] = [Approve("site", "h1", "a"), Approve("price", "p1", "a")]
    assert approved(BUILD, events)
    rewritten = Built("site", "h2", (OWNER, AREA), False)
    reused = Built("price", "p1", PRICE.sentences, True)
    after = states((rewritten, reused, EMPTY), events)
    assert (after["site"], after["price"]) == (State.IN_REVIEW, State.APPROVED)
    assert not approved((rewritten, reused, EMPTY), events)


def test_a_deliverable_with_nothing_in_it_is_not_approved() -> None:
    assert not approved((EMPTY,), [])


def test_a_comment_follows_the_facts_of_its_sentence_through_a_rewrite() -> None:
    on_owner = Comment("site", "h1", "a", "which deed?", ("site.owner",))
    on_area = Comment("site", "h1", "a", "surveyed?", ("site.area",))
    whole = Comment("site", "h1", "a", "too short", to_agent=True)
    elsewhere = Comment("price", "p1", "a", "check")
    rewritten = Built("site", "h2", (Sentence("Owner: {site.owner}.", ("site.owner",)),), False)
    kept = comments(rewritten, [on_owner, on_area, whole, elsewhere, Approve("site", "h2", "a")])
    assert kept == (on_owner, whole)
