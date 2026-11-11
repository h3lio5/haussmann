from haussmann.ctxkit.search import Index, best_passage, words
from haussmann.docparse.elements import Element

ELEMENTS = (
    Element("plu", "p1", "Dispositions générales applicables à la zone."),
    Element("plu", "p8", "La hauteur maximale des constructions est fixée à 9 m."),
    Element("bail", "p1", "Le loyer s'élève à 3 000 € par an. Le bail prend fin en 2027."),
    Element("plaquette", "p1", "Hauteur possible : 15 m. Hauteur, hauteur, hauteur."),
    Element("vide", "p1", ""),
)
INDEX = Index(ELEMENTS)


def found(query: str, k: int = 5) -> list[str]:
    return [f"{hit.element.doc_id}:{hit.element.locator}" for hit in INDEX.search(query, k)]


def test_words_drop_case_accents_punctuation_and_single_letters() -> None:
    assert words("L'Élévation à 9 m, côté RUE") == ["elevation", "cote", "rue"]


def test_search_finds_elements_sharing_words_with_the_query() -> None:
    assert set(found("hauteur maximale")) == {"plu:p8", "plaquette:p1"}
    assert found("loyer du bail") == ["bail:p1"]


def test_accents_and_case_do_not_matter() -> None:
    assert found("GENERALES") == ["plu:p1"]


def test_a_rare_word_outranks_a_repeated_common_one() -> None:
    assert found("hauteur maximale")[0] == "plu:p8"


def test_k_limits_the_results_and_no_match_gives_nothing() -> None:
    assert len(found("hauteur", k=1)) == 1
    assert found("piscine") == []
    assert Index(()).search("hauteur", 3) == []


def test_results_are_stable_across_calls() -> None:
    assert found("hauteur maximale des constructions") == found(
        "hauteur maximale des constructions"
    )


def test_best_passage_starts_at_the_line_that_shares_most_words_with_the_query() -> None:
    text = "Dispositions générales.\nLa hauteur est libre. La hauteur maximale est de 9 m.\nFin."
    assert best_passage(text, "hauteur maximale", 100) == "La hauteur maximale est de 9 m. Fin."
    assert best_passage(text, "hauteur maximale", 12) == "La hauteur m"
    assert best_passage(text, "piscine", 100).startswith("Dispositions générales.")
    assert best_passage("", "hauteur", 100) == ""
    assert best_passage("[Sheet1!A6] Sous-sol\n[Sheet1!B6] 310 m²", "sous-sol", 50).startswith(
        "[Sheet1!A6] Sous-sol"
    )
