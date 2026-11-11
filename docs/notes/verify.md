# verify: checking and settling facts

Status: written and implemented 2026-11-11; open to revision.

## Where this fits

Fact-finders are language models, so what they write to the ledger is a set of claims. `verify` is the step that turns claims into facts the memo may use. It is all ordinary code: no model is called, so the same ledger always gives the same result, and a number the model made up cannot get through.

```
candidate facts ──> citation check ──> verified / unverified
                         │
        verified facts ──┴──> same key, different values? ──> conflict ──> rule ──> winner or escalation
                                                                             
        declared totals ──> sum of settled parts ──> computed fact ──> compared with any stated total
```

The two baselines failed here most clearly: they copied a wrong total every time and never reported a disagreement with both sources.

## Boundaries

```python
check_fact(fact, elements, renderings) -> str | None        # None: holds; otherwise the reason
value_appears(value, text, renderings=()) -> bool
passage(elements, citation) -> str | None                   # the page, cell or document cited

verify(ledger, elements, cards, schema, keys, totals, renderings) -> None   # appends to the ledger
settled(ledger, key, schema) -> Settled(key, fact, supporting, conflict, reasons)
```

Example: the ledger holds `max_height = 9 m` citing the regulation (authority 3) and `max_height = 15 m` citing a brochure (authority 1). Both pass the citation check. `verify` records a conflict and resolves it to the first with the reason "higher-authority source". `settled` returns the 9 m fact, both facts as supporting, and that reason.

## Decisions

**The citation check is literal.** A fact passes when the cited page, cell or document exists and states the value: a quantity as a number written there, a date in a numeric form or a form the workload supplies, text as the same words ignoring case, accents and punctuation. When the finder gave a quote, the quote must be in the passage and the value in the quote. There is no model fallback yet: a fact that fails is unverified and is not used. This is strict on purpose, since it is the only thing between a model's claim and the memo.

**Numbers are read the way documents write them.** Digits grouped by spaces are one number, and a comma or a dot is the decimal mark. A form like `1.200` is ambiguous and is accepted as either reading.

**Every citation of a fact must hold.** A fact with one good and one bad citation is unverified. Finders record one source per fact, so this costs nothing and keeps bad citations out of the memo.

**Disagreement is decided by rule, in a fixed order.** A value recomputed from its parts beats a stated one; then the source of higher authority; then the later source. If the best two are equal on all three, the conflict is escalated to a person and no value is used. The order and the reason are recorded with the resolution.

**Authority and dates come from document cards,** so the platform compares integers and dates and knows nothing about document types.

**Totals are declared, not discovered.** The caller says which key is the sum of which parts. The total is computed only when every part is settled in the right unit; otherwise a stated total, if any, stands on its own.

**The same value from several sources is agreement.** Values are compared in the canonical unit within the attribute's tolerance, so `0,12 ha` and `1 200 m²` are one value.

## Tests

- Citation check: one case per way a citation can fail and per value kind; French number forms.
- Settling: unverified facts are left out; authority, then date, then escalation; agreement across units; a wrong stated total loses to the recomputed one; no total while a part is missing.

## Known limits

- **A true value written differently fails the check.** A date spelled in a form nobody supplied, or a paraphrased name, is unverified. The planned fallback is a model judging whether the passage supports the value, used only after the literal check fails.
- **A number that appears for another reason passes.** "9" on a page with nine of something satisfies a quantity of 9 when no quote is given.
- **Running `verify` twice on one ledger records the same conflicts twice.** A run calls it once.

## Alternatives rejected

- **A model as the first-line checker.** It is the component being checked.
- **Letting an agent resolve every conflict.** Most conflicts fall to a rule a person can read; an agent is kept for the escalated ones.
- **Majority vote across sources.** Three brochures would outvote one regulation.
