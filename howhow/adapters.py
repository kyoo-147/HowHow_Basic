"""Phase E1 clean-room adapter contracts.

Adapters exchange immutable, hash-bound JSON envelopes. They never execute an
upstream project and the doctor only reads optional checkouts.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .core import atomic_json, canonical, now, sha256_bytes, safe_id
from .vnext import REPOS

REPO_PINS = {name: sha for name, sha, _ in REPOS}
# Paths are the reviewed contract surfaces, not claims that a checkout exists.
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / 'fixtures' / 'phase-e1'
FIXTURE_SLUGS = {name: name.lower().replace(' ', '-') for name in REPO_PINS}


def _fixture_record(repo: str) -> dict[str, Any]:
    path = FIXTURE_ROOT / FIXTURE_SLUGS[repo] / 'manifest.json'
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise SystemExit(f'missing E1 source fixture for {repo}: {path}') from exc
    if record.get('repository') != repo or not record.get('source_file') or len(record.get('source_sha256', '')) != 64:
        raise SystemExit(f'invalid E1 source fixture for {repo}')
    source = FIXTURE_ROOT / FIXTURE_SLUGS[repo] / record['source_file']
    if not source.is_file() or sha256_bytes(source.read_bytes()) != record['source_sha256']:
        raise SystemExit(f'E1 source fixture hash mismatch for {repo}')
    return record


# Every surface is one concrete file captured at the reviewed upstream pin.
# The fixture is an exact byte snapshot; no checkout is required to use a contract.
SURFACES = {name: [_fixture_record(name)['source_file']] for name in REPO_PINS}
LICENSE_FILES = ['LICENSE', 'LICENSE.md', 'COPYING', 'NOTICE']
OPERATIONS = {
    'wanshuiyin ARIS': ['stage-state', 'idea-dossier', 'evidence-reviewer-receipt', 'experiment-bridge', 'result-to-claim', 'research-wiki-export', 'research-wiki-import'],
    'Randall ARIS': ['legacy-compatibility'], 'AI-Researcher': ['idea-request', 'candidate-import'],
    'AgentLaboratory': ['literature-phase', 'plan-phase', 'data-phase', 'experiment-phase', 'interpretation-phase', 'writing-phase', 'skeptical-review-checkpoint'], 'AI-Scientist': ['idea-metadata', 'template-metadata', 'run-metadata', 'writeup-metadata', 'review-metadata', 'template-run-writeup'],
    'gpt-researcher': ['retrieval-request', 'candidate-output'], 'deer-flow': ['sandbox-request', 'sandbox-result'],
    'sciagent': ['scientific-qc'], 'autoresearch': ['baseline-ledger'],
    'Academic-Paper-Skills': ['paper-conformance'], 'latex-arxiv-SKILL': ['latex-conformance'],
    'OpenScholar': ['rerank-synthesis'], 'DeepScientist': ['quest-run'],
}
RESTRICTIONS = {
    'AI-Researcher': ['REFERENCE_ONLY pending license clarification', 'Windows filename limitation is explicit', 'provisional novelty/feasibility/completeness only; no novelty verdict'],
    'AI-Scientist': ['disabled by default', 'custom-license restricted-use acknowledgement and manuscript AI disclosure required', 'never execute on host'],
    'deer-flow': ['disabled by default', 'OS/container isolated profile only', 'memory/checkpoint is never canonical'],
    'sciagent': ['REFERENCE_ONLY pending operative license file', 'prompt-only guardrails are not enforcement'],
    'OpenScholar': ['offline only', 'no fetching/model download/public server/citation promotion', 'Contriever CC-BY-NC boundary'],
    'DeepScientist': ['daemon/worktree/memory remains external', 'Windows support limitation is explicit'],
}


def contract(repo: str) -> dict[str, Any]:
    if repo not in REPO_PINS: raise SystemExit('unknown pinned repository: ' + repo)
    fixture = _fixture_record(repo)
    return {'repository': repo, 'pin': REPO_PINS[repo],
            'required_upstream_files': [{'path': fixture['source_file'], 'sha256': fixture['source_sha256'],
                                         'fixture': str(Path('fixtures/phase-e1') / FIXTURE_SLUGS[repo] / fixture['source_file']).replace('\\', '/') }],
            'operations': OPERATIONS[repo], 'restrictions': RESTRICTIONS.get(repo, []),
            'import_state': 'PROVISIONAL', 'live_status': 'NOT_CALLED'}


def contracts() -> list[dict[str, Any]]: return [contract(name) for name in REPO_PINS]


def _adapt(repo: str, operation: str, payload: Any) -> Any:
    if operation not in OPERATIONS[repo]: raise SystemExit('unsupported operation for ' + repo + ': ' + operation)
    if not isinstance(payload, dict): raise SystemExit('adapter payload must be an object')
    result = dict(payload)
    result.setdefault('cross_links', [])
    result['adapter_operation'] = operation
    result['provisional'] = True
    if repo == 'AI-Researcher':
        result.setdefault('novelty', 'PROVISIONAL'); result.setdefault('feasibility', 'PROVISIONAL'); result.setdefault('completeness', 'PROVISIONAL')
    if repo == 'Randall ARIS': result['lineage'] = {'translated_from': 'Randall ARIS', 'current_contract': 'wanshuiyin ARIS'}
    if repo == 'AI-Scientist': result.setdefault('enablement', {'restricted_use_acknowledged': False, 'manuscript_ai_disclosure': False})
    if repo == 'OpenScholar': result.setdefault('fetching', False); result.setdefault('model_download', False)
    return result


def export_contract(repo: str, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = _adapt(repo, operation, payload)
    envelope = {'schema_version': 1, 'kind': 'howhow-adapter-envelope', 'repository': repo,
                'pin': REPO_PINS[repo], 'operation': operation, 'payload': body,
                'payload_sha256': sha256_bytes(canonical(body)), 'created_at': now(),
                'state': 'PROVISIONAL', 'raw_adapter_receipt': payload}
    envelope['envelope_sha256'] = sha256_bytes(canonical(envelope))
    return envelope


def validate_import(envelope: dict[str, Any], known_ids: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(envelope, dict) or envelope.get('kind') != 'howhow-adapter-envelope': raise SystemExit('invalid adapter envelope')
    if envelope.get('schema_version') != 1 or envelope.get('state') != 'PROVISIONAL':
        raise SystemExit('adapter envelope must use schema_version 1 and PROVISIONAL state')
    repo = envelope.get('repository'); pin = envelope.get('pin')
    if repo not in REPO_PINS or pin != REPO_PINS[repo]: raise SystemExit('wrong repository pin')
    if envelope.get('operation') not in OPERATIONS[repo]: raise SystemExit('unsupported adapter operation')
    payload = envelope.get('payload')
    if envelope.get('payload_sha256') != sha256_bytes(canonical(payload)): raise SystemExit('adapter payload hash mismatch')
    expected = dict(envelope); supplied = expected.pop('envelope_sha256', None)
    if supplied != sha256_bytes(canonical(expected)): raise SystemExit('adapter envelope hash mismatch')
    if not isinstance(payload, dict) or not payload.get('provisional', False): raise SystemExit('adapter imports must remain provisional')
    links = payload.get('cross_links', [])
    if not isinstance(links, list) or not all(isinstance(link, str) and link for link in links):
        raise SystemExit('adapter cross_links must be a list of non-empty IDs')
    if known_ids is not None:
        missing = sorted(set(links) - known_ids)
        if missing: raise SystemExit('adapter cross-link not found: ' + ', '.join(missing))
    if repo == 'AI-Scientist':
        enablement = payload.get('enablement', {})
        if enablement.get('restricted_use_acknowledged') is not True or enablement.get('manuscript_ai_disclosure') is not True:
            raise SystemExit('AI-Scientist restricted-use acknowledgement and manuscript AI disclosure are required')
    if repo == 'OpenScholar' and (payload.get('fetching') is True or payload.get('model_download') is True):
        raise SystemExit('OpenScholar imports must be offline and cannot fetch or download models')
    if repo in {'DeepScientist', 'AI-Scientist'} and payload.get('restricted_use_acknowledged') is not True and repo == 'DeepScientist':
        raise SystemExit('DeepScientist restricted-use acknowledgement is required')
    return {'valid': True, 'repository': repo, 'pin': pin, 'state': 'PROVISIONAL', 'cross_link_validation': 'VALIDATED'}


def import_contract(root: Path, envelope: dict[str, Any]) -> dict[str, Any]:
    known_ids = set()
    for path in (root / '.howhow').rglob('*.json'):
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(value, dict) and isinstance(value.get('id'), str): known_ids.add(value['id'])
        except (OSError, ValueError):
            continue
    result = validate_import(envelope, known_ids)
    safe_id(envelope.get('operation', ''), 'operation')
    receipt = dict(envelope)
    receipt['imported_at'] = now(); receipt['validation'] = result
    receipt_id = 'receipt-' + sha256_bytes(canonical(receipt))[:16]
    receipt['receipt_id'] = receipt_id
    atomic_json(root / '.howhow/integrations/receipts' / (receipt_id + '.json'), receipt)
    return result | {'receipt_id': receipt_id, 'raw_receipt_retained': True}


def _checkout_candidates(root: Path, repo: str) -> list[Path]:
    slug = repo.lower().replace(' ', '-').replace('_', '-')
    bases = [root / '.howhow/checkouts', Path(os.environ.get('HOWHOW_CHECKOUTS', '')) if os.environ.get('HOWHOW_CHECKOUTS') else None,
             Path.home() / '.cache/checkouts']
    return [base / slug for base in bases if base and (base / slug).is_dir()] + [base / repo for base in bases if base and (base / repo).is_dir()]


def doctor(root: Path) -> dict[str, Any]:
    rows = []
    manifest = root / '.howhow/integration-manifest.json'
    manifest_items = {x.get('name'): x for x in (json.loads(manifest.read_text(encoding='utf-8')).get('integrations', []) if manifest.exists() else [])}
    for repo, pin, _ in REPOS:
        checkout = next(iter(_checkout_candidates(root, repo)), None)
        configured = manifest_items.get(repo, {})
        row: dict[str, Any] = {'repository': repo, 'expected_pin': pin, 'checkout': str(checkout) if checkout else None,
                               'enabled': bool(configured.get('enabled', False)), 'live': configured.get('live_status') == 'CALLED', 'conformance': 'NOT_RUN', 'license_status': configured.get('license_status', 'UNKNOWN'),
                               'platform': platform.system(), 'runtime': sys.version.split()[0], 'dependency_ready': False}
        if checkout is None:
            row['state'] = 'AVAILABLE_CONTRACT_NOT_INSTALLED'; row['conformance'] = 'AVAILABLE_CONTRACT_NOT_INSTALLED'; rows.append(row); continue
        try: head = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError): head = None
        row['actual_head'] = head; row['pin_match'] = head == pin
        row['license_status'] = 'OPERATIVE_FILE_PRESENT' if any((checkout / f).is_file() for f in LICENSE_FILES) else 'LICENSE_FILE_MISSING'
        required = []
        for item in contract(repo)['required_upstream_files']:
            target = checkout / item['path']; present = target.exists(); is_file = target.is_file()
            actual_hash = sha256_bytes(target.read_bytes()) if is_file else None
            required.append({'path': item['path'], 'expected_sha256': item['sha256'], 'present': present,
                             'hash_checked': is_file, 'actual_sha256': actual_hash,
                             'hash_match': (actual_hash == item['sha256']) if is_file else None})
        row['required_files'] = required
        row['dependency_ready'] = shutil.which('git') is not None
        row['required_files_match'] = all(x['present'] and x['hash_checked'] and x['hash_match'] for x in required)
        row['state'] = 'CONFORMANT_NOT_ENABLED' if row['pin_match'] and row['license_status'] != 'LICENSE_FILE_MISSING' and row['required_files_match'] else 'CHECKOUT_NONCONFORMANT'
        row['conformance'] = row['state']; rows.append(row)
    return {'schema_version': 1, 'read_only': True, 'checked_at': now(), 'integrations': rows}
