"""Fixed-width MIR record generator."""
from math import ceil
from typing import Dict, Iterable, List, Tuple

import config
from api_enrichment import enrich_claim
from mir_layout import HEADER, PAYMENT_REDUCTION_SLOTS, SERVICE, Field
from mir_mapper import claim_primary_reason, map_header, map_service, signed_amount
from models import Claim, ServiceLine


def _put(buffer: List[str], field: Field, value: str, align: str = "left") -> None:
    value = "" if value is None else str(value)
    if len(value) > field.length:
        value = value[:field.length]
    if align == "right":
        value = value.rjust(field.length, config.BLANK_CHAR)
    else:
        value = value.ljust(field.length, config.BLANK_CHAR)
    start = field.start - 1
    buffer[start:start + field.length] = list(value)


def _header(claim: Claim, sequence: int, max_sequence: int, line_count: int) -> str:
    b = [config.BLANK_CHAR] * config.MIR_HEADER_LENGTH
    enrichment = enrich_claim(claim) if config.API_ENRICHMENT_ENABLED else {}
    values = map_header(claim, sequence, max_sequence, line_count, enrichment)
    for name, field in HEADER.items():
        _put(b, field, values.get(name, ""))
    result = "".join(b)
    if len(result) != config.MIR_HEADER_LENGTH:
        raise ValueError(f"Header generated with invalid length {len(result)}")
    return result


def _service_block(service: ServiceLine, claim_status: str, inherited_reason: str = "") -> str:
    b = [config.BLANK_CHAR] * config.MIR_SERVICE_BLOCK_LENGTH
    values = map_service(service, claim_status, inherited_reason)
    for name, field in SERVICE.items():
        _put(b, field, values.get(name, ""))

    reductions = values["payment_reductions"]
    for slot, slot_fields in PAYMENT_REDUCTION_SLOTS.items():
        amount = reductions.get(slot)
        if amount is None:
            _put(b, slot_fields["reason"], "")
            _put(b, slot_fields["amount"], config.SIGNED_ZERO_AMOUNT)
        else:
            code = f"{config.PAYMENT_REDUCTION_CODE_PREFIX}{slot}"
            _put(b, slot_fields["reason"], code)
            _put(b, slot_fields["amount"], signed_amount(amount))

    result = "".join(b)
    if len(result) != config.MIR_SERVICE_BLOCK_LENGTH:
        raise ValueError(f"Service block generated with invalid length {len(result)}")
    return result


def generate_mir_records(claims: Iterable[Claim]) -> Tuple[List[str], Dict[str, int]]:
    records: List[str] = []
    total_claims = 0
    total_services = 0
    split_claims = 0

    for claim in claims:
        total_claims += 1
        services = claim.services or []
        total_services += len(services)

        # Maintain a record even if a claim has no SVC line.  Overflow behavior
        # is configurable in config.py so production rules can change centrally.
        if config.SERVICE_OVERFLOW_MODE == "truncate":
            chunks = [services[:config.MAX_SERVICE_LINES_PER_RECORD]] if services else [[]]
        elif config.SERVICE_OVERFLOW_MODE == "split":
            chunks = [services[i:i + config.MAX_SERVICE_LINES_PER_RECORD]
                      for i in range(0, len(services), config.MAX_SERVICE_LINES_PER_RECORD)] or [[]]
        else:
            raise ValueError(
                f"Unsupported SERVICE_OVERFLOW_MODE={config.SERVICE_OVERFLOW_MODE!r}; "
                "use 'split' or 'truncate'."
            )

        max_sequence = len(chunks)
        if max_sequence > 1:
            split_claims += 1
        if max_sequence > config.MAX_RECORD_SEQUENCE:
            raise ValueError(
                f"Claim {claim.claim_number} requires {max_sequence} MIR records; "
                f"configured maximum is {config.MAX_RECORD_SEQUENCE}."
            )

        for sequence, chunk in enumerate(chunks, start=1):
            inherited_reason = claim_primary_reason(claim)
            if config.SERVICE_OVERFLOW_MODE == "truncate" and len(services) > config.MAX_SERVICE_LINES_PER_RECORD:
                header_service_count = len(services) % 100
            else:
                header_service_count = len(chunk)
            record = _header(claim, sequence, max_sequence, header_service_count)
            record += "".join(_service_block(svc, claim.status, inherited_reason) for svc in chunk)
            expected = config.MIR_HEADER_LENGTH + len(chunk) * config.MIR_SERVICE_BLOCK_LENGTH
            if len(record) != expected:
                raise ValueError(
                    f"Claim {claim.claim_number} record {sequence}: expected length {expected}, got {len(record)}"
                )
            records.append(record)

    return records, {
        "claims": total_claims,
        "services": total_services,
        "mir_records": len(records),
        "split_claims": split_claims,
    }


def generate_mir_text(claims: Iterable[Claim]) -> Tuple[str, Dict[str, int]]:
    records, summary = generate_mir_records(claims)
    # MIR sample is one fixed-width record per physical line.
    text = "\r\n".join(records)
    if records:
        text += "\r\n"
    return text, summary
