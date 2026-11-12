# buildkit: the deliverable as a build

Status: written and implemented 2026-11-12; open to revision.

## Where this fits

After `verify`, the ledger holds one settled fact per key, the disagreements and the open questions. `buildkit` turns that state into a deliverable made of sections, and does it the way a build system does: each section is a target with a hash over its inputs, and a target whose hash is unchanged is not rebuilt.

```
settled ledger ──(workload: bind)──> inputs ──> select per section ──> Target(hash)
                                                                         │
                                         cache hit ──> stored section    │ miss
                                                                         ▼
                                                       author (model or code) ──> Built section
```

- **Called by**: the workload's run, once after verification, and again after an expert edit.
- **Needed because**: a memo rewritten in full after each correction costs a model call per section and changes sentences the expert already approved. A build rewrites only what the correction touches, and the list of what was rebuilt is the diff the reviewer sees.
- **Imports**: `coretypes` only. It never reads the ledger itself; the workload hands it inputs. This keeps it usable for any deliverable and keeps formatting (French numbers, dates) out of the platform.

## Structures

```python
@dataclass(frozen=True, slots=True)
class Section:
    id: str
    title: str
    kind: str                      # which author writes it: "prose", "disagreements", "open"
    attributes: tuple[str, ...]    # the inputs it selects
    guidance: str = ""             # writing guidance, part of the hash

@dataclass(frozen=True, slots=True)
class Spec:
    id: str
    version: str
    sections: tuple[Section, ...]

@dataclass(frozen=True, slots=True)
class Input:
    name: str                      # stable across runs: "site.land_area", "lease:atelier.annual_rent"
    attribute: str                 # what sections select on
    text: str                      # the value as it will be printed, formatted by the workload
    digest: str                    # canonical value, flag reasons and citations, as one string
    flagged: bool = False

@dataclass(frozen=True, slots=True)
class Target:
    section: Section
    inputs: tuple[Input, ...]      # sorted by name
    hash: str

@dataclass(frozen=True, slots=True)
class Sentence:
    text: str                      # with placeholders: "Le terrain mesure {site.land_area}."
    uses: tuple[str, ...]          # input names

@dataclass(frozen=True, slots=True)
class Built:
    section_id: str
    hash: str
    sentences: tuple[Sentence, ...]
    reused: bool

type Author = Callable[[Target], Awaitable[Sequence[Sentence]]]

targets(spec, inputs, environment: Mapping[str, str]) -> tuple[Target, ...]
async build(targets, authors: Mapping[str, Author], cache: MutableMapping[str, tuple[Sentence, ...]]) -> tuple[Built, ...]
fill(sentence, inputs, flag_mark) -> str   # placeholders replaced by each input's text
```

`environment` holds whatever else the text depends on and the platform cannot know: prompt version, model id.

## The hash

```
sha256( canonical JSON of {
    spec: spec.id, version: spec.version,
    section: id, title, kind, guidance,
    environment: sorted items,
    inputs: [ [name, digest] for each input, sorted by name ]
} )
```

Canonical JSON: sorted keys, no spaces, UTF-8. The digest is computed by the workload from the fact's canonical value (a quantity in its canonical unit, a date in ISO form), its flag reasons and its citations, each sorted.

## Invariants

- The order in which inputs arrive never changes a hash.
- Changing one input changes the hash of exactly the sections that select its attribute.
- Ledger fact ids are not in the hash and not in a stored sentence. The same fact found again in a new run reuses the section; a sentence names its inputs, and the current fact behind a name is looked up when the memo is rendered or reviewed.
- An input's printed `text` is not hashed separately; it is a function of the digest's value and the workload's formatter, and a change of formatter is a change of `environment`.
- A stored section holds placeholders, not values. Values are substituted at render time from the inputs the hash was computed over.
- `build` calls an author only on a cache miss, and writes the cache only after the author returns. A failed author leaves the cache as it was.
- Every section of the spec has an author for its kind; `build` refuses a spec that does not.

## Alternatives rejected

- **Hash the whole ledger state.** Any new fact would rebuild every section, which is the behaviour the build exists to avoid.
- **Fact ids as placeholders.** Ids are assigned in order of recording, so two runs that find the same facts give different ids, different prompts and no reuse.
- **Sections select facts by key.** Subjects differ between files; a spec that named `lease:atelier` would fit one file.
- **Let `buildkit` read the ledger.** It would then need the value kinds, the formatter and the notion of a settled fact. Handing it plain inputs keeps one direction of dependency and makes the hashing testable without a ledger.
- **A dependency graph between sections.** No section reads another section today. The targets are independent; a graph is added when a summary section exists.

## Tests

- Property: any permutation of the inputs gives the same hashes.
- Property: changing the digest of one input changes the hash of the sections that select its attribute and no other.
- Changing the spec version, a section's guidance or an environment entry changes the affected hashes.
- A second `build` with the same targets calls no author and marks every section reused.
- After one input changes, only the affected sections are rewritten; the others are returned from the cache.
- An author that raises leaves the cache unchanged.
- `fill` replaces every placeholder, marks a flagged input and refuses a sentence that uses an unknown name.
- A section with no input is empty and calls no author; a spec whose kind has no author is refused.
