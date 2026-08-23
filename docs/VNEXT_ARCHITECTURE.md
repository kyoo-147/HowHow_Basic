# HowHow vNext Phase A architecture

Phase A is a project-local, standard-library Python thin vertical slice. The CLI is deterministic and short-lived; Pi remains responsible for interpretation and human scientific judgment. There is no daemon, web UI, hidden worker, automatic publication, novelty verdict, or full-text/live capability matrix.

## Boundaries

- `.howhow/` is the canonical immutable record store. Corrections create new IDs/revisions and hash events.
- `OPINION.md` is a human preference channel only. It has states `MISSING`, `EMPTY`, and `PRESENT`; opinion is never evidence, approval, novelty, or publication permission.
- Integration research is represented by 13 pinned manifest entries. The current wanshuiyin ARIS pin is upstream authority; Randall ARIS is an older fork/compatibility snapshot. No ambiguous or restricted code is copied.
- Capabilities are explicitly classified `AVAILABLE`, `ADAPTED_SKILL`, `ADAPTER`, `REFERENCE_ONLY`, `RESTRICTED`, or `BLOCKED`, with enabled/live state. Reference entries are never called live.
- Briefs, ideas, rankings, selections, targets, and claim maps are records. Consequential transitions require an explicit user confirmation/selection record.
- Idea ranking is deterministic and occurs only after safety, ethics, license, data, evaluator, resource, and evidence gates. Three to five eligible candidates are required; rejected candidates and reasons remain recorded. Rank 1 recommends but does not authorize execution and no novelty claim is made.
- Paper targets are provisional at selection and confirmed later. They contain suggested words/pages/figures/tables, rationale, venue constraints, and user decision; no fixed page range is imposed. An argument skeleton may be non-prose.
- Claim maps record section/paragraph IDs, claim type (`EXTERNAL`, `EMPIRICAL`, `INTERPRETIVE`, `HYPOTHESIS`, `LIMITATION`, `OPINION`), support/contradiction links, uncertainty, and source/run references. Integrity audit is deterministic; human scientific review remains separate.

## Flow

`start` -> inspect capabilities and sources -> propose/confirm brief -> add 3–5 gated ideas -> rank -> record user selection -> propose target -> confirm target -> add/audit claims -> human review. `continue` presents the next bounded step and never fabricates model-generated ideas.

The existing experiment runner is `TRUSTED_LOCAL`, not a security sandbox. Live adapters and full-text work are deferred.
