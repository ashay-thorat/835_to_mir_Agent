"""Deterministic claim search over parsed 835 data."""
import difflib
from typing import Iterable, List, Sequence

import config
from models import Claim

_SEARCH_FIELDS = (
    "claim_number",
    "claim_reference",
    "patient_last_name",
    "patient_first_name",
    "patient_middle",
    "subscriber_id",
    "group_number",
)


def _claim_values(claim: Claim) -> List[str]:
    return [
        str(getattr(claim, field) or "") for field in _SEARCH_FIELDS
    ]


def _match_token_exact(values: List[str], token: str) -> bool:
    """Return True if token matches any field value as a whole word.

    A 'whole word' match means the token equals the full field value or equals
    one of the whitespace-separated words inside a field value.  This prevents
    'john' from matching 'johnny'.
    """
    for value in values:
        lowered = value.lower()
        # Full field match  (e.g. token="john", field="john")
        if token == lowered:
            return True
        # Word-level match  (e.g. token="john", field="john a")
        if token in lowered.split():
            return True
    return False


def search_claims(claims: Iterable[Claim], query: str) -> List[Claim]:
    text = (query or "").strip().lower()
    if not text:
        return []

    tokens = text.split()
    results: List[Claim] = []

    for claim in claims:
        values = _claim_values(claim)

        # Every token the user typed must match at least one field as a whole word.
        if all(_match_token_exact(values, token) for token in tokens):
            results.append(claim)

    return results


def filter_claims(
    claims: Iterable[Claim],
    min_amount=None,
    max_amount=None,
    status: str = "",
) -> List[Claim]:
    result: List[Claim] = []
    for claim in claims:
        if min_amount is not None and claim.total_paid < min_amount:
            continue
        if max_amount is not None and claim.total_paid > max_amount:
            continue
        if status and claim.status != status:
            continue
        result.append(claim)
    return result
