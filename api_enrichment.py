"""Enrichment of MIR header fields from the parsed 835.

The converter intentionally does not invent values that are not present in the
835, so the two MIR header dates are derived from the claim's own service dates
(the earliest and latest across its lines).  If a claim has no service dates,
both are left blank.
"""
from typing import Dict

from models import Claim


def enrich_claim(claim: Claim) -> Dict[str, str]:
    service_dates = [svc.service_date for svc in claim.services if svc.service_date]
    return {
        "api_date_1": min(service_dates) if service_dates else "",
        "api_date_2": max(service_dates) if service_dates else "",
    }
