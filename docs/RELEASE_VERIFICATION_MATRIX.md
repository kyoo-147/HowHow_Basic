# Release and verification matrix

The matrix separates product integrity from scientific and publication decisions. The synthetic detailed fixture is generated only inside the E2E test and is never a research result.

| Layer | Evidence | What it proves | What it does not prove |
|---|---|---|---|
| Unit tests | `tests/test_*.py` | Record, hash, gate, adapter, audit, and fail-closed contracts | Live providers or scientific correctness |
| Deterministic detailed fixture | `tests/test_vnext_detailed_e2e.py`; `verify --profile vnext-detailed --strict` | Complete conversational/state path, D1/D2 records, LaTeX/package rebuild, tamper rejection | A real episode, findings, novelty, or human review |
| Optional integration conformance | `integration contracts`, provisional export/import receipts, `integration doctor` | Exact-pin surface and envelope contracts; doctor is read-only | Installation, live execution, or upstream scientific validity |
| Live APIs | Explicit `source search`/`source add` receipts | A bounded official API response was retrieved and hashed | Completeness, correctness, novelty, or acceptance |
| Real experiment | Approved proposal/grant and retained execution records | A declared bounded command ran under its stated trust boundary | Scientific validity or generalization |
| Human scientific review | Human-owned review and decision records | Human judgment of claims, methods, uncertainty, novelty, and ethics | Automatic product verification |
| Submission authorization | Explicit human/venue authorization outside HowHow | Permission to submit | Any guarantee of acceptance |

`READY_FOR_HUMAN_REVIEW` means only that the selected product profile and package gates passed. It never means scientifically correct, novel, peer reviewed, publication-ready, or authorized for submission.
