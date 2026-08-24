# HowHow Basic implementation notes

- The authoritative product boundary is the approved CLI review in the discovery artifacts: one project-local CLI and `.howhow/`, no daemon, web UI, hidden worker, automatic publication, or novelty verdict.
- The Python package in `howhow/` is intentionally dependency-free; use the standard library so the control plane remains portable.
- Keep source payloads, evidence, experiment records, and failures immutable. Correct a record by creating a new ID/revision.
- Run tests with `python -m unittest discover -s tests -v` and product validation with `python -m howhow verify --strict` from a project directory.
- The Phase F detailed fixture is `tests/test_vnext_detailed_e2e.py`; it is synthetic/test-only and must never be described as a real research result.
- Keep `PROJECT_STATUS.md` evidence-backed and distinguish deterministic fixtures, live APIs, and human review boundaries.
