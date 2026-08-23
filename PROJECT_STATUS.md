# HowHow Basic status

Updated 2026-08-23 after a live product-path run in `projects/claimledger/`.

## Evidence-backed completion

**Overall MVP completion: 92% (implemented product and deterministic/local acceptance).** This percentage is a capability estimate, not scientific acceptance. Against the broader autonomous research-to-LaTeX acceptance, the product remains partial because task execution and scientific review are intentionally human-owned.

| Capability | Status | Evidence |
|---|---|---|
| Project-local conversational CLI and filesystem state | VERIFIED_DETERMINISTIC | `howhow init`, status, pause/resume, continuation, atomic JSON state |
| Plans, human gate, checkpoints, append-only events | VERIFIED_LIVE | `projects/claimledger/.howhow/events.jsonl`; human continuation returned `NEEDS_HUMAN` and accepted an explicit response |
| Source registry and safe cached retrieval | VERIFIED_LIVE | local CC0 fixture plus official OpenAlex REST response, raw payload hashes and manifests |
| Exact evidence spans and audit | VERIFIED_LIVE | `ev-corpus-span-1`, strict audit passed; negative altered-span test is in unit tests and failure memory |
| Experiment records and preserved failure | VERIFIED_LIVE | deterministic CPU benchmark success plus `claimledger-benchmark-failed-001` and failure log |
| Research scaffold and role prompts | VERIFIED_DETERMINISTIC | `.pi/skills/howhow-basic`, `.pi/agents`, `schemas`, project layout |
| LaTeX build and source package | VERIFIED_LIVE | MiKTeX `pdflatex`/`bibtex`, 4-page `dist/paper.pdf`, `dist/arxiv-source.tar.gz` |
| Record-driven render/finalization gate | VERIFIED_LIVE | `paper render` emits `paper/howhow_records.tex`; `paper finalize` strictly audits records, builds LaTeX, validates archive extraction, then records `COMPLETE` |
| Claims/reviews/gates and truthful readiness | PARTIAL | claim map and machine review report exist; no human scientific review, novelty decision, or external submission |
| Parallel Pi-subagent waves | PARTIAL | role prompts and development schedule exist; product has no hidden worker and no live multi-agent wave evidence |
| Full API adapter matrix (arXiv, OpenAlex, Crossref, Semantic Scholar) | PARTIAL | OpenAlex live retrieval and arXiv search adapter implemented; Crossref/S2 remain future adapters |
| Sandboxed arbitrary experiment execution | NOT IMPLEMENTED | records are accepted; the CLI intentionally does not add a hidden runner/daemon |


## Completion boundaries (evidence-backed)

- **Implemented product:** 92%; locking, bounded local/HTTP source reads, redirect fail-closed checks, exact VERIFIED spans, claim-to-run links, scaffold-safe LaTeX rendering, and reproducibility supplements are implemented and tested.
- **Deterministic E2E:** 100% of the bounded ClaimLedger demonstration; strict verification is `READY_FOR_HUMAN_REVIEW`, not scientific acceptance.
- **Scientific human review:** 0% complete; human inspection of claims, limitations, novelty, and correctness remains required.
- **External submission:** 0%; no submission or publication action was performed.

## End-to-end product evidence

Topic: **ClaimLedger: a CPU-only controlled benchmark for detecting stale evidence links**. This is a feasible community-useful systems reproducibility topic, but the controlled mutation is synthetic and the result is not a novelty or universal-validity claim.

Commands run successfully:

```text
python -m unittest discover -s tests -v                         # exit 0
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

## Residual gaps

- Human review and direction/novelty/correctness judgment remain required later.
- The product does not yet provide a sandboxed arbitrary-code runner, statistical uncertainty engine, or independent immutable review-record CLI.
- Crossref and Semantic Scholar adapters, rebuild verification, and full claim-linter coverage are future work. Source archive extraction/hash validation is now part of finalization.
- The experiment uses one short local fixture, one mutation, and one repetition; timing is descriptive only.
