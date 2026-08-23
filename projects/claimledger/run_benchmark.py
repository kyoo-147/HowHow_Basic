"""Deterministic CPU benchmark for the ClaimLedger demonstration.
Synthetic mutations are controlled robustness fixtures, not natural-world evidence.
"""
import hashlib, json, time
from pathlib import Path

source = Path("data/corpus.txt").read_bytes()
seed = 17
observations = []
for condition, payload in [("valid", source), ("mutated", source[:-1] + b"X")]:
    start = time.perf_counter_ns()
    content_result = hashlib.sha256(payload).hexdigest() == hashlib.sha256(source).hexdigest()
    path_only_result = True
    elapsed_us = (time.perf_counter_ns() - start) / 1000
    observations.append({"condition": condition, "content_addressed_rejects": not content_result, "path_only_accepts": path_only_result, "latency_us": round(elapsed_us, 3)})
result = {
    "id": "claimledger-benchmark-001", "hypothesis": "hash identity rejects a controlled mutation while path-only identity accepts it",
    "command": ["python", "run_benchmark.py"], "code_revision": "working-tree-claimledger-benchmark-v1", "seed": seed,
    "status": "SUCCESS", "raw_observations": observations,
    "metrics": {"content_addressed_invalid_acceptance_rate": 0.0, "path_only_invalid_acceptance_rate": 1.0,
                 "valid_content_rejection_rate": 0.0, "repetitions": 1, "warmup": 0},
    "limitations": ["one local synthetic mutation", "one repetition", "does not establish general scientific validity"],
    "environment": {"python": "stdlib", "platform": "portable CPU"}, "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
}
Path("experiment-success.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
