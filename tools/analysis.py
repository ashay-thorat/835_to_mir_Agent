"""Structured 835 analysis used as session context.

Only derived, deterministic facts go here.  The raw 835 is never sent to the
LLM; this summary is what the agent reasons over.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

import config
from edi835_parser import parse_835
from models import Claim


def _elements(tag: str, text: str) -> List[List[str]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if "~" in normalized:
        raw = normalized.replace("\n", "").split("~")
    else:
        raw = normalized.split("\n")
    result: List[List[str]] = []
    for segment in raw:
        parts = segment.strip().split("*")
        if parts and parts[0].upper() == tag:
            result.append(parts)
    return result


def _first_name(parts: List[str]) -> str:
    # NM1*PR*1*PAYERNAME*... : NM102, NM103 (name), NM104 (first name), NM108/NM109 (id).
    name = parts[3].strip() if len(parts) > 3 else ""
    qualifier = parts[8].strip() if len(parts) > 8 else ""
    identifier = parts[9].strip() if len(parts) > 9 else ""
    if qualifier:
        return f"{name} ({qualifier}:{identifier})".strip()
    return name


def _format_amount(value: Decimal) -> str:
    return f"{value:,.2f}"


def analyze_835(text: str) -> Dict[str, Any]:
    claims: List[Claim] = parse_835(text)
    payer_parts = _elements("NM1", text)
    payer = ""
    for parts in payer_parts:
        if len(parts) > 1 and parts[1].upper() == "PR":
            payer = _first_name(parts)
            break
    transactions = len(_elements("ST", text))

    total_charge = sum(c.total_charge for c in claims)
    total_paid = sum(c.total_paid for c in claims)
    members = sorted({c.subscriber_id for c in claims if c.subscriber_id})
    patients = sorted(
        {f"{c.patient_last_name}, {c.patient_first_name}".strip(" ,")
         for c in claims if c.patient_last_name}
    )
    dates = [c.claim_received_date for c in claims if c.claim_received_date]
    date_min = min(dates) if dates else ""
    date_max = max(dates) if dates else ""

    preview = []
    for claim in claims:
        preview.append(
            {
                "claim_number": claim.claim_number,
                "claim_reference": claim.claim_reference,
                "patient": f"{claim.patient_last_name} {claim.patient_first_name}".strip(),
                "status": claim.status,
                "total_charge": _format_amount(claim.total_charge),
                "total_paid": _format_amount(claim.total_paid),
            }
        )

    return {
        "file_type": "835",
        "transactions": transactions,
        "claim_count": len(claims),
        "total_charge": _format_amount(total_charge),
        "total_paid": _format_amount(total_paid),
        "payer": payer or "Unknown",
        "member_ids": members,
        "member_count": len(members),
        "patients": patients,
        "patient_count": len(patients),
        "received_date_min": date_min,
        "received_date_max": date_max,
        "preview_claims": preview,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def format_analysis_report(analysis: Dict[str, Any]) -> str:
    lines = [
        f"835 analysis completed. Claims found: {analysis['claim_count']}",
        f"Transactions (ST): {analysis['transactions']}",
        f"Total charge: {analysis['total_charge']}",
        f"Total paid:   {analysis['total_paid']}",
        f"Payer: {analysis['payer']}",
        f"Unique members: {analysis['member_count']}",
        f"Unique patients: {analysis['patient_count']}",
    ]
    if analysis["received_date_min"]:
        lines.append(
            f"Claim received dates: {analysis['received_date_min']} .. {analysis['received_date_max']}"
        )
    preview = analysis["preview_claims"]
    if preview:
        lines.append("Preview of first claims:")
        for item in preview:
            patient = item["patient"] or "(no patient name)"
            lines.append(
                f"  {item['claim_number']} | {patient} | paid {item['total_paid']}"
            )
    return "\n".join(lines)
