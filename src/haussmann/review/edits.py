"""An expert's correction, as a ledger transaction."""

from haussmann.coretypes.values import FactKey, Schema, Value, normalize
from haussmann.ledger.ledger import Assess, Ledger, NewFact, Status
from haussmann.verify.settle import EXPERT


class EditRefused(ValueError):
    pass


def edit(
    ledger: Ledger, key: FactKey, value: Value, reason: str, author: str, schema: Schema
) -> str:
    """Record the expert's value for a key and return the new fact's id.

    The fact is written as verified, with the expert's reason. Which fact a key settles on
    is decided afterwards by `verify`, where an expert's fact counts above every other.
    """
    attribute = schema.get(key.attribute)
    if attribute is None or normalize(value, attribute) is None:
        raise EditRefused(f"the value does not fit {key.subject}/{key.attribute}")
    if not reason.strip() or not author.strip():
        raise EditRefused("an edit needs a reason and an author")
    fact_id = f"f{len(ledger.facts()) + 1}"
    ledger.append(
        author,
        [NewFact(key, value, (), EXPERT), Assess(fact_id, Status.VERIFIED, reason)],
    )
    if ledger.facts()[-1].id != fact_id:
        raise EditRefused("the ledger gave the edit another id than expected")
    return fact_id
