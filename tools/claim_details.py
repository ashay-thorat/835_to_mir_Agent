"""Deterministic claim display formatting.

The LLM never generates claim lists or amounts.  These formatters turn the
structured claim data into the exact text shown to the user, so nothing can be
invented.
"""
from typing import List

from models import Claim


def _patient_name(claim: Claim) -> str:
    name = f"{claim.patient_last_name} {claim.patient_first_name}".strip()
    return name or "(no patient name)"


def format_claim_list(claims: List[Claim]) -> str:
    if not claims:
        return "No claims found."
    lines = []
    for index, claim in enumerate(claims, start=1):
        status = f" status={claim.status}" if claim.status else ""
        lines.append(
            f"{index}. {claim.claim_number} — paid {claim.total_paid:,.2f}{status}"
        )
    return "\n".join(lines)


def format_claim_detail(claim: Claim) -> str:
    lines = [
        f"Claim number:  {claim.claim_number or '(none)'}",
        f"Claim ref:     {claim.claim_reference or '(none)'}",
        f"Patient:       {_patient_name(claim)}",
        f"Member ID:     {claim.subscriber_id or '(none)'}",
        f"Group number:  {claim.group_number or '(none)'}",
        f"Status:        {claim.status or '(none)'}",
        f"Total charge:  {claim.total_charge:,.2f}",
        f"Total paid:    {claim.total_paid:,.2f}",
        f"Patient resp.: {claim.patient_responsibility:,.2f}",
        f"Service lines: {len(claim.services)}",
        f"Received date: {claim.claim_received_date or '(none)'}",
    ]
    if claim.services:
        lines.append("Services:")
        for svc in claim.services:
            paid = f"paid {svc.paid:,.2f}"
            lines.append(f"  - {svc.procedure or '(no proc)'} | {svc.charge:,.2f} | {paid}")
    return "\n".join(lines)
