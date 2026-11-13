from haussmann.buildkit.build import Built, Sentence
from haussmann.buildkit.targets import Input
from haussmann.review.diff import SectionDiff, ValueChange, diff

MARK = " (to check)"


def item(name: str, text: str, flagged: bool = False) -> Input:
    return Input(name, name.split(".")[-1], text, text, flagged)


def section(section_id: str, digest: str, *sentences: str) -> Built:
    made = tuple(
        Sentence(text, tuple(part.split("}")[0] for part in text.split("{")[1:]))
        for text in sentences
    )
    return Built(section_id, digest, made, False)


OLD = {i.name: i for i in (item("site.owner", "Town"), item("site.area", "1 200 m²"))}
SITE = section("site", "h1", "The owner is {site.owner}.", "The land measures {site.area}.")
PRICE = section("price", "p1", "No price is stated.")


def test_a_build_compared_with_itself_has_no_difference() -> None:
    assert diff([SITE, PRICE], [SITE, PRICE], OLD, OLD, MARK) == ()


def test_a_changed_value_is_reported_with_the_sentence_that_prints_it() -> None:
    new = {**OLD, "site.owner": item("site.owner", "County")}
    rebuilt = section("site", "h2", "The owner is {site.owner}.", "The land measures {site.area}.")
    assert diff([SITE, PRICE], [rebuilt, PRICE], OLD, new, MARK) == (
        SectionDiff(
            "site",
            True,
            (ValueChange("site.owner", "Town", "County"),),
            ("The owner is Town.",),
            ("The owner is County.",),
        ),
    )


def test_a_flag_that_appears_is_a_change_of_what_is_printed() -> None:
    new = {**OLD, "site.area": item("site.area", "1 200 m²", flagged=True)}
    rebuilt = section("site", "h2", "The owner is {site.owner}.", "The land measures {site.area}.")
    (changed,) = diff([SITE], [rebuilt], OLD, new, MARK)
    assert changed.values == (ValueChange("site.area", "1 200 m²", "1 200 m² (to check)"),)
    assert changed.added == ("The land measures 1 200 m² (to check).",)


def test_a_fact_that_enters_or_leaves_a_section_and_a_section_that_disappears() -> None:
    new = {**OLD, "site.zone": item("site.zone", "Uc")}
    rebuilt = section("site", "h3", "The owner is {site.owner}.", "The zone is {site.zone}.")
    site, price = diff([SITE, PRICE], [rebuilt], OLD, new, MARK)
    assert site.values == (
        ValueChange("site.area", "1 200 m²", None),
        ValueChange("site.zone", None, "Uc"),
    )
    assert (site.removed, site.added) == (("The land measures 1 200 m².",), ("The zone is Uc.",))
    assert price == SectionDiff("price", True, (), ("No price is stated.",), ())


def test_every_reported_value_change_is_in_a_section_marked_rewritten() -> None:
    new = {**OLD, "site.owner": item("site.owner", "County")}
    rebuilt = section("site", "h2", "Owner: {site.owner}.", "The land measures {site.area}.")
    assert all(d.rewritten for d in diff([SITE, PRICE], [rebuilt, PRICE], OLD, new) if d.values)
