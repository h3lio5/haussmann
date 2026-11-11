import re
from pathlib import Path

PLATFORM_ROOT = Path(__file__).parent.parent / "src" / "haussmann"

BANNED_TERMS = (
    "parcel",
    "cadastre",
    "zoning",
    "lease",
    "tenant",
    "landlord",
    "rent",
    "deed",
    "easement",
    "dataroom",
)

BANNED_ACRONYMS = ("PLU",)

_BANNED = re.compile(
    r"(?<![A-Za-z])(?:(?i:" + "|".join(BANNED_TERMS) + r")s?|" + "|".join(BANNED_ACRONYMS) + r")"
    r"(?![A-Za-z])"
)


def find_domain_terms(root: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in {".py", ".md"}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in _BANNED.finditer(line):
                hits.append(f"{path.relative_to(root)}:{number}: {match.group(0)}")
    return hits


def test_platform_has_no_domain_vocabulary() -> None:
    assert find_domain_terms(PLATFORM_ROOT) == []


def test_scan_reports_a_planted_term(tmp_path: Path) -> None:
    (tmp_path / "clean.py").write_text("current = release = indeed = 1\n", encoding="utf-8")
    (tmp_path / "leaky.py").write_text("x = 1\ndef monthly_rent() -> int: ...\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("Each Tenant has leases, plus a PLU.\n", encoding="utf-8")

    assert find_domain_terms(tmp_path) == [
        "leaky.py:2: rent",
        "notes.md:1: Tenant",
        "notes.md:1: leases",
        "notes.md:1: PLU",
    ]
