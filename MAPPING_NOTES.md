# Current 835 → MIR Mapping Notes

## Claim header

| MIR area | 835 source / rule | Status |
|---|---|---|
| Record Type | `MO` from `config.py` | Constant |
| Claim number | `CLP01` | Direct |
| Claim reference | `CLP07` | Direct |
| Header API date 1 | Not reliably present in supplied 835 | Blank/API |
| Header API date 2 | Not reliably present in supplied 835 | Blank/API |
| Claim status | `CLP02` | Direct |
| Primary denial/edit reason | First CAS group+reason when status is not paid | Derived |
| Member ID | `NM1*IL` member ID, configurable 12-char normalization | Direct/format |
| Group | `REF*1L` | Direct |
| Patient name | `NM1*QC` | Direct |
| DOB | `DTM*036` | Direct |
| Sequence/max sequence | Split service lines in groups of configured max 50 | Derived |
| Service count | Number of SVC lines in current MIR record | Derived |

## Service block

| MIR area | 835 source / rule | Status |
|---|---|---|
| Status | Claim `CLP02` | Direct |
| Primary reason | First CAS group+reason for non-paid claims | Derived |
| Units | `SVC05`, default 1 | Direct/default |
| Service charge | `SVC02` | Direct |
| Covered charge | Service charge minus CO adjustment(s), not below zero | Derived |
| Paid amount | `SVC03` | Direct |
| Patient liability | Covered charge minus paid amount, not below zero | Derived |
| PR1..PR10 | CAS group PR, reason numbers 1..10 map to corresponding MIR slots | Direct/format |
| Other unknown numeric fields | MIR fixed numeric default | Default |
| Unknown character fields | spaces | Blank/API |
