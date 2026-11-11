"""Keyword search over elements, ranked with BM25."""

import math
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from haussmann.docparse.elements import Element

K1 = 1.5
B = 0.75


def words(text: str) -> list[str]:
    """Lower-case words without accents; single characters are dropped."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(
        char if char.isalnum() else " " for char in decomposed if not unicodedata.combining(char)
    )
    return [word for word in plain.casefold().split() if len(word) > 1]


@dataclass(frozen=True, slots=True)
class Hit:
    element: Element
    score: float


class Index:
    """Built once per document set; `search` is a pure lookup."""

    def __init__(self, elements: Sequence[Element]) -> None:
        self._elements = tuple(elements)
        self._counts = [Counter(words(element.text)) for element in self._elements]
        self._lengths = [sum(counts.values()) for counts in self._counts]
        self._average = sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        self._containing = Counter(word for counts in self._counts for word in counts)

    def search(self, query: str, k: int) -> list[Hit]:
        """The `k` best elements for the query, best first; elements with no match are left out."""
        terms = set(words(query))
        total = len(self._elements)
        hits: list[tuple[float, int]] = []
        for position, counts in enumerate(self._counts):
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if frequency == 0:
                    continue
                containing = self._containing[term]
                rarity = math.log(1 + (total - containing + 0.5) / (containing + 0.5))
                length = self._lengths[position] / self._average if self._average else 0.0
                score += rarity * frequency * (K1 + 1) / (frequency + K1 * (1 - B + B * length))
            if score > 0:
                hits.append((score, position))
        hits.sort(key=lambda hit: (-hit[0], hit[1]))
        return [Hit(self._elements[position], score) for score, position in hits[:k]]
