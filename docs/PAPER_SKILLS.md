# HowHow paper skills adaptation

HowHow Basic adapts the paper-writing and paper-policy methodology from **DELONG-L/Academic-Paper-Skills**, inspected at pin `d67bf46aa3a0176847a2749ce84e99d556021f20`. This is an attribution and contract record, not copied upstream text or code. The adapted contract is: organize a substantive manuscript checklist; require paragraph claim anchors; distinguish source-supported, empirical, interpretive, opinion, and unresolved material; disclose uncertainty, negative results, limitations, ethics/rights/dual-use, and reproducibility inputs; and retain immutable revisions. HowHow's paper context is the only input and adapted skills never invent evidence. The translated D2 contract adds immutable figure/table provenance, citation identity-versus-support checks, typed issue execution contracts, preserved dissent, and policy/license/disclosure review. These skills consume immutable context only.

## Inspected upstream material

- Repository: `DELONG-L/Academic-Paper-Skills`
- Pin: `d67bf46aa3a0176847a2749ce84e99d556021f20`
- Inspected files: upstream paper-writing skill/index and paper-policy/checklist materials at that pin (upstream checkout was not imported into this repository).
- Local translated contract: `howhow/paper.py`, section types and `audit()`.
- Conformance test: `tests/test_paper.py` and `tests/test_d2.py`; fixture E2E is explicitly non-scientific.

## latex-arxiv-SKILL adaptation

The local clean-room workflow adapts appautomaton/latex-arxiv-SKILL at pin `349ce88a0797422911a4ce58ed335842e9b87e15`: approved plan before prose, typed issue execution contract, deterministic citation-preserving compile/refinement checks, and extracted source-package QA. It does not submit to a venue. MIT notices are preserved where applicable; IEEEtran remains governed by its LPPL boundary and is not vendored.
- Commit pin: this project records the exact upstream commit; unavailable upstream file bytes are not represented as local evidence.

## Notices

The adapted contract is project documentation; the materialized repository notice is [`NOTICE`](../NOTICE). Any third-party upstream license text and notices remain the responsibility of the upstream repository; no upstream code or substantial text is redistributed here. This feature does not make novelty, correctness, acceptance, or publication decisions.
