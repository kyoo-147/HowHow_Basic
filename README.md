# HowHow Basic

HowHow Basic is a small, project-local, conversational research control plane. It is deliberately a CLI rather than a daemon or web application. The main Pi HowHow agent owns interpretation and human interaction; this repository owns durable filesystem records, hashes, append-only events, checkpoints, evidence audits, experiment manifests, LaTeX builds, and source packaging.

## Install / run

```powershell
python -m howhow init projects/demo --goal "Evaluate a bounded, reproducible systems question"
python -m howhow status --json
python -m howhow source search --provider arxiv --query "reproducible research provenance" --limit 3
python -m howhow verify --profile project
python -m howhow paper finalize
```

From a project directory, use the installed module or the explicit source-tree entrypoint: `python -m pip install -e D:/work/navin/research_agent/howhow_basic` then `python -m howhow ...`, or `python D:/work/navin/research_agent/howhow_basic/bin/howhow.py ...`. If the Scripts directory warning says `howhow.exe` is not on PATH, use the module/source-tree form. VERIFIED text evidence uses zero-based, end-exclusive UTF-8 character offsets; `char_end` excludes the trailing newline. `pip install -e .` installs the `howhow` executable. No network, model, database, daemon, or hidden worker is required for local operation. Network retrieval uses official arXiv/OpenAlex endpoints only and records raw responses when explicitly added.

## Product boundary

Commands are intentionally short-lived: `init`, `source add|search|list`, `plan save|show`, `continue`, `status`, `pause`, `resume`, `evidence add|audit`, `experiment record`, `paper build`, `package`, and `verify`. Retrieved content is untrusted data. The CLI never creates scientific conclusions, automatic novelty judgments, publication claims, or arXiv submissions.

## Records and truth model

Every project has `.howhow/` with an atomic state snapshot and mission budget, append-only hash-chained `events.jsonl`, immutable source payload/manifest directories, evidence descriptors, experiment records, failures, build logs, verification reports, and distribution artifacts. The project scaffold also contains `phases/`, `waves/`, `tasks/`, and `attempts/` records with idempotency keys so Pi wave recipes can use typed artifacts without becoming canonical state owners. `VERIFIED` is reserved for evidence that the product re-read the exact source bytes and matched the exact locator; fixture and imported data remain separately labeled. Failed and inconclusive runs are retained.

`READY_FOR_HUMAN_REVIEW` means deterministic product gates passed and a human can inspect a complete package. `paper finalize` renders retained records, runs strict verification, builds the manuscript, validates archive extraction and hashes, and only then records project state `COMPLETE`. Neither state means scientifically correct, novel, accepted, peer reviewed, or eligible for arXiv. Publication remains human-owned.

## Role and wave prompts

Project Pi roles live in `.pi/agents/`: director, literature, worker, and reviewer. The existing `.pi/subagents/schedules/` file is development automation only; it is not required by the product. Parallel waves should dispatch independent typed tasks through the configured Pi subagent harness and merge only immutable descriptors through the sole canonical writer.

## Development

```powershell
python -m unittest discover -s tests -v
python -m py_compile howhow/*.py
```

The complete end-to-end evidence example is documented in `PROJECT_STATUS.md` and under `projects/claimledger/`. It uses official OpenAlex metadata, a CC0 local source fixture for exact-span checks, a deterministic CPU benchmark, a deliberately preserved failed run, and a multi-page LaTeX paper. This is a product demonstration, not a scientific acceptance or publication claim.

Review findings are recorded separately with `review add`, audited with `review audit --strict`, and summarized with `review status`. They are immutable, bind to a claim and retained source span and/or experiment run, and never create scientific conclusions.
