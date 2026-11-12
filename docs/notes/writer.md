# Writer: prose around bound facts

Status: written and implemented 2026-11-12; open to revision.

## Where this fits

The writer is the author of the prose sections of a deliverable. `buildkit.build` calls it for each section whose hash changed. It is the only step after verification that calls a model, and it is built so that the model cannot change a fact.

```
Target(section, inputs) ──> prompt: guidance + list of placeholders with their printed values
                                │
                              model ──> sentences with placeholders
                                │
                              check (code) ──fail──> one retry with the reasons ──fail──> plain list (code)
                                │ pass
                              Sentence(text, uses)
```

- **Called by**: `build`, through the `Author` type, for sections of kind "prose".
- **Needed because**: the two baselines show what a model does when it writes values itself: it copies a wrong total and converts units in its head. Here the model chooses words and order; code supplies every value.
- **Split**: the check, retry and fallback are platform code in `buildkit`. The prompt, the French formatter and the two sections written from ledger state are in the workload.

## Structures

```python
# buildkit
type Ask = Callable[[Target, Sequence[str]], Awaitable[Sequence[str]]]   # target, reasons of a refused draft -> sentences
check(sentences: Sequence[str], inputs: Sequence[Input]) -> list[str]     # reasons; empty when the draft holds
plain(target: Target) -> tuple[Sentence, ...]                             # "<label> : {name}." per input
prose_author(ask: Ask, label: Callable[[Input], str]) -> Author

# workload
memo_ask(client, model, sample) -> Ask        # one structured call: {"sentences": ["...", ...]}
bind(ledger, asked, schema) -> inputs         # one per settled fact, disagreement, flag and open question
# the two ledger-driven sections use buildkit's `listing` author: each input is printed as bound
```

What the model receives for one section:

```
Section : Règles d'urbanisme
Consigne : <guidance>
Faits à utiliser, chacun au moins une fois, par son nom entre accolades :
- {site.zone} = "Uc"
- {site.max_height} = "8 m"
- {site.planning_certificate_date} = "12 février 2024"  (signalé : certificat expiré)
```

What it returns: `{"sentences": ["Le terrain est classé en zone {site.zone}.", ...]}`.

## The check

A draft is refused, with the reason given back to the model, when:

1. a placeholder names something that is not an input of the section;
2. an input of the section is used in no sentence;
3. a digit appears outside a placeholder;
4. a sentence has no placeholder at all (prose with no fact behind it has no place in a section of facts).

One retry. If the second draft is refused, the section is the plain list, built by code. A section therefore always builds, and a run reports how many sections needed the retry or the list.

## Flags are printed by code

When an input is flagged (a disagreement, a recomputed total, an expired date), the renderer prints its value followed by a fixed mark that points to the "Points to resolve" section. The model is told the fact is flagged so that it can word the sentence accordingly, but whether the reader sees the warning does not depend on the model.

## Sections written by code

- **Points to resolve**: one entry per disagreement and per date flag, with each side's value, its documents and the rule that decided, or the statement that it is left to the reviewer.
- **Open questions**: one entry per required fact with nothing settled.

Their text is composed when the ledger is bound, as inputs of their own attribute, and the sections print those inputs through a listing author. They go through the same hash and cache as the prose sections.

## Invariants

- No value in a rendered memo was typed by the model: every digit comes from an input's printed text or from the fixed wording of code-written sections.
- Every input of a prose section appears in it.
- Every sentence of a prose section records the inputs it uses; this record is what the review interface follows from a sentence to its sources.
- The model call is the only non-deterministic step, and it is recorded and replayed like every other call.

## Known limits

- A number written in words ("deux étages") passes the digit check. The guidance forbids it; code does not catch it.
- The check does not judge whether a sentence says something true about a fact, only that it uses it. A sentence that calls a disputed value certain is caught by the printed flag, not by the wording. Prose quality is not scored in this slice.
- The plain list is correct and unreadable as prose. Its rate is reported, not hidden.

## What the first run showed

E010 built the memo of the three dev scenarios: 18 prose sections, 59 settled facts, all stated, no digit typed by the model, 0.0007 USD and about ten seconds per memo.

Five sections of 18 fell back to the plain list, against a target of fewer than one in ten. All eleven refused drafts have the same cause. In a section with one or two facts the model fills the paragraph with sentences that have no fact behind them: "Ce montant pourrait évoluer en fonction des négociations", "Des études spécifiques ont été menées pour évaluer ce risque". Some restate a value in words without its placeholder ("Aucun risque d'inondation n'est signalé" for a fact whose value is "non"). None of this is in the file. The fourth rule of the check exists for this and refused every one; the second draft usually repeated the fault.

Two things passed that should not have:

- A clause with nothing behind it inside a sentence that does name a fact: "Le terrain se situe en zone {site.zone} selon le plan local d'urbanisme".
- The model's own caution next to a flagged fact ("à vérifier pour son actualité", "signalé"), printed beside the mark that code adds, so the warning appears twice.

Both are wording, not values, and both are the limit already stated: the check knows that a sentence uses a fact, not what it says about it.

## Alternatives rejected

- **Free prose, then extract and verify the numbers.** It checks after the fact what can be prevented, and a wrong number that happens to equal another fact passes.
- **A second model as critic.** It adds cost and a second source of variation before there is a measure of prose quality to justify it. The code checks cover what can be decided without judgment.
- **Templates only, no model.** Correct and cheap, and it is the fallback. Kept as the fallback rather than the default because a memo of generated lists is not what an expert is asked to sign.
- **One call for the whole memo.** One changed fact would then rewrite every section, and a failed check would discard all of them.

## Tests

- `check` refuses, each with its reason: an unknown placeholder, an unused input, a digit outside a placeholder, a sentence without a placeholder; and accepts a draft that holds.
- A refused first draft is retried once with the reasons; a refused second draft gives the plain list.
- A flagged input is rendered with the mark whatever the sentence says.
- The code-written sections list every disagreement and every open key, and nothing else.
- End to end on recorded drafts: the rendered memo of each dev scenario contains no digit that is not in an input's text or in fixed wording.
