"""MIR conversion tool.

Reuses the existing deterministic 835 -> MIR converter.  The agent only
selects which claims to convert; all record building happens here.
"""
from typing import Any, Dict, List, Tuple
from pathlib import Path

from edi835_parser import parse_835
from mir_generator import generate_mir_records, generate_mir_text
from models import Claim


def generate_mir_texts(claims: List[Claim], claim_numbers: List[str]) -> List[Tuple[Claim, str, Dict]]:
    by_number = {c.claim_number: c for c in claims}
    missing = [n for n in claim_numbers if n not in by_number]
    if missing:
        raise ValueError(
            "The following claim numbers were not found in the 835 file: "
            + ", ".join(missing)
        )
    results: List[Tuple[Claim, str, Dict]] = []
    for number in claim_numbers:
        claim = by_number[number]
        if not claim.services:
            raise ValueError(
                f"Claim {claim.claim_number} has no service lines, so an MIR "
                "record cannot be built."
            )
        mir_text, summary = generate_mir_text([claim])
        results.append((claim, mir_text, summary))
    return results


def count_summary(claims: List[Claim]) -> str:
    return "\n".join(
        f"{c.claim_number} | {c.patient_last_name} {c.patient_first_name}".strip()
        + f" | paid {c.total_paid:,.2f}"
        for c in claims
    )


def convert_835_to_mir_file(input_file_path: str | Path, output_file_path: str | Path) -> Dict[str, Any]:
    input_path = Path(input_file_path)
    output_path = Path(output_file_path)
    
    text = input_path.read_text(encoding="utf-8", errors="replace")
    claims = parse_835(text)
    
    if not claims:
        return {
            "success": False,
            "message": "No claims found in the file",
            "total_claims": 0,
            "converted_claims": 0,
            "failed_claims": 0,
        }
    
    generated: List[str] = []
    failed_claims = 0
    for claim in claims:
        if not claim.services:
            failed_claims += 1
            continue
        try:
            records, _ = generate_mir_records([claim])
            generated.extend(records)
        except Exception:
            failed_claims += 1
            
    if not generated:
        return {
            "success": False,
            "message": "No claims could be converted to MIR",
            "total_claims": len(claims),
            "converted_claims": 0,
            "failed_claims": failed_claims,
        }
        
    combined_text = "\r\n".join(generated) + "\r\n"
        
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(combined_text, encoding="ascii", errors="replace", newline="")
    except Exception as exc:
        return {
            "success": False,
            "message": f"Failed to write output file: {exc}",
            "total_claims": len(claims),
            "converted_claims": len(claims) - failed_claims,
            "failed_claims": failed_claims,
        }
        
    # Verify file
    if not output_path.is_file() or output_path.stat().st_size == 0:
        return {
            "success": False,
            "message": "Generated file is empty or missing",
            "total_claims": len(claims),
            "converted_claims": len(claims) - failed_claims,
            "failed_claims": failed_claims,
        }
        
    return {
        "success": True,
        "message": "835 converted to MIR successfully",
        "total_claims": len(claims),
        "converted_claims": len(claims) - failed_claims,
        "failed_claims": failed_claims,
        "file_name": output_path.name,
    }
