# HowHow Basic status

Updated 2026-08-23 after adding the Phase E1 pinned ecosystem adapter contracts and read-only conformance doctor.

## Evidence-backed status

Status is described by evidence and boundaries rather than completion percentages. Phase E1 is implemented as local, deterministic contracts and tests; no upstream checkout is claimed live. Phase 0 is the deterministic ClaimLedger fixture and existing local control plane. vNext Phase A is the thin vertical slice: empty opinion state, 13 differentiated manifest-backed capability entries and pinned integrations, confirmation-gated immutable brief/target revisions, hard-gated 3–5 idea ranking and selection, provisional argument-skeleton targets, and claim-map integrity audit including retained source/run hashes. Phase B adds deterministic, immutable literature protocol/candidate/decision/matrix/transformed-source records, a bounded gpt-researcher adapter contract, exact evidence requirements, contradiction search and explicit unresolved coverage audit. No real research episode has occurred. Phase D1 adds immutable paper-context snapshots, anchored section imports, and a substantive content-contract audit. Phase D2 adds fail-closed figure/table provenance manifests, citation identity-vs-support records, immutable issue/revision/dissent records, and policy/license/disclosure inventory. `verify --profile vnext-detailed` requires D1 substantive content plus all D2 classes; `fixture` remains legacy compatibility and is never advertised as a detailed research episode. The fixture is deterministic and explicitly non-scientific; it demonstrates product gates only. A real research episode and human scientific review are separate activities; publication is not performed or authorized by this product.

| Capability | Status | Evidence |
|---|---|---|
| Project-local conversational CLI and filesystem state | VERIFIED_DETERMINISTIC | `howhow init`, status, pause/resume, continuation, atomic JSON state |
| Plans, human gate, checkpoints, append-only events | VERIFIED_LIVE | `projects/claimledger/.howhow/events.jsonl`; human continuation returned `NEEDS_HUMAN` and accepted an explicit response |
| Source registry and safe cached retrieval | VERIFIED_LIVE | local CC0 fixture plus official OpenAlex REST response, raw payload hashes and manifests |
| Exact evidence spans and audit | VERIFIED_LIVE | `ev-corpus-span-1`, strict audit passed; descriptor hashes and referenced experiment contents are revalidated, with negative span/claim/run-binding tests |
| Experiment records and preserved failure | VERIFIED_LIVE | deterministic CPU benchmark success plus `claimledger-benchmark-failed-001` and failure log; strict verification revalidates every record hash, filename/id binding, required field, and status payload |
| Research scaffold and role prompts | VERIFIED_DETERMINISTIC | `.pi/skills/howhow-basic`, `.pi/agents`, `schemas`, project layout |
| LaTeX build and source package | VERIFIED_LIVE | MiKTeX `pdflatex`/`bibtex`, 4-page `dist/paper.pdf`, `dist/arxiv-source.tar.gz`; the archive with all 15 hashed members compiles from a temporary extracted directory |
| Record-driven render/finalization gate | VERIFIED_LIVE | `paper render` emits `paper/howhow_records.tex`; `paper finalize` strictly audits records, builds LaTeX, safely extracts and recompiles the source archive, then records `READY_FOR_HUMAN_REVIEW` |
| Claims/reviews/gates and truthful readiness | PARTIAL | claim map, D1 audit, and D2 immutable issue/artifact/citation/policy audits exist; machine review is explicitly not independent scientific review; no human scientific review, novelty decision, or external submission |
| Parallel Pi-subagent waves | PARTIAL | role prompts and development schedule exist; product has no hidden worker and no live multi-agent wave evidence |
| Full API adapter matrix (arXiv, OpenAlex, Crossref, Semantic Scholar) | PARTIAL | OpenAlex live retrieval and arXiv search adapter implemented; Crossref/S2 remain future adapters |
| Bounded arbitrary experiment execution | VERIFIED_DETERMINISTIC_PARTIAL | v1 remains backward compatible. Phase C adds immutable analysis/proposal/grant/result bindings, one-shot consumption, mutation checks, prebuilt-lock doctor, RECORD_ONLY/TRUSTED_LOCAL profiles, and truthful non-sandbox limitations. It is not an OS sandbox and does not prevent host filesystem or network access. |


## Completion boundaries (evidence-backed)

- **Implemented product:** Existing locking, bounded local/HTTP source reads, redirect fail-closed checks, exact VERIFIED spans, evidence and claim-to-run integrity checks, bounded local experiment execution, review-target revalidation, scaffold-safe LaTeX rendering, and reproducibility supplements are implemented and tested.
- **Deterministic E2E:** The bounded ClaimLedger demonstration has a clean-copy integration test covering render, strict verification, manuscript build, package creation, safe extraction, and clean-room recompilation. `READY_FOR_HUMAN_REVIEW` remains an inspectable package gate only.
- **Scientific human review:** Required and not performed by the CLI; human inspection of claims, limitations, novelty, and correctness remains separate.
- **External submission:** Not performed; publication is outside product scope.

## End-to-end product evidence

Topic: **ClaimLedger: a CPU-only controlled benchmark for detecting stale evidence links**. This is a feasible community-useful systems reproducibility topic, but the controlled mutation is synthetic and the result is not a novelty or universal-validity claim.

Commands run successfully:

```text
python -m unittest discover -s tests -v                         # exit 0, 16 tests
python -m py_compile howhow/*.py                                # exit 0
python -m howhow source add data/corpus.txt --license CC0         # exit 0
python -m howhow source add https://api.openalex.org/...         # exit 0, live official metadata retrieval
python -m howhow evidence audit --strict                         # exit 0
python run_benchmark.py                                          # exit 0, real deterministic CPU run
python -m howhow experiment record experiment-success.json      # exit 0
python -m howhow experiment record experiment-failure.json       # exit 0, preserved negative control
python -m howhow paper build --strict                            # exit 0, MiKTeX
python -m howhow package --strict                                # exit 0
python -m howhow verify --strict --profile project              # exit 0, READY_FOR_HUMAN_REVIEW
python -m howhow paper render                                  # exit 0, generated record ledger
python -m howhow paper finalize                                # exit 0, COMPLETE gate
```

The final exact product verdict is `READY_FOR_HUMAN_REVIEW`. It means the deterministic gates and local package are inspectable. It does **not** mean accepted, correct, novel, peer reviewed, scientifically generalizable, or eligible for arXiv. No external submission was made. When all plan tasks are exhausted, `paper finalize` records `COMPLETE` only after record rendering, strict verification, LaTeX build, and source-archive extraction/hash validation; `COMPLETE` still retains the human-review boundary.

## Phase E1 evidence

`howhow integration contracts` emits all 13 pin-bound contracts and surface hashes. `howhow integration doctor` is read-only and reports missing checkouts as `AVAILABLE_CONTRACT_NOT_INSTALLED`. Export/import tests cover every repository, wrong pins, envelope/payload tampering, restricted AI-Scientist acknowledgement/disclosure, raw receipt retention, and provisional-only state. The optional checkout doctor does not clone, execute, or mutate caches. Contract fixtures do not represent live upstream execution or scientific validation.

## Residual gaps

- Human review and direction/novelty/correctness judgment remain required later; D2 records preserve dissent and machine/model context but do not constitute independent scientific review. The legacy demo has no D2 detailed package and must not be read as completed review.
- The bounded runner is not an OS security sandbox: trusted commands may still access host files and the network, and child-process-tree teardown is not independently enforced. Hostile-code isolation and a statistical uncertainty engine remain unimplemented. Independent immutable review records provide claim/evidence-bound findings, and strict project verification includes their hash-chain and retained-target integrity audit as a named `reviews` check.
- Crossref and Semantic Scholar adapters and full claim-linter coverage are future work. Phase A record writers enforce the brief, idea, and claim contracts; strict project verification also reports malformed persisted Phase A records and invalid source/run bindings. Source archive extraction, member-hash validation, and clean-room LaTeX recompilation are now part of finalization and CI.
- The experiment uses one short local fixture, one mutation, and one repetition; timing is descriptive only.

Independent immutable review records are implemented with claim/evidence binding, strict hash-chain audit, and repeat validation of retained source spans and experiment records. Every retained experiment, including unlinked failures and inconclusive results, is independently hash- and schema-checked by project verification. These gates record integrity, not correctness, novelty, or publication readiness.
