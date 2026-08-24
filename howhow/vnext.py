from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import atomic_json, canonical, now, sha256_bytes, append_event, safe_id, sha256_file, read_json

REPOS = [('wanshuiyin ARIS','9cbb6aab1084cd622ccb016cc156008fbdaa1402','upstream authority'),('Randall ARIS','10394e53e8651efcbedccd377c878e3ba929c3d4','older fork/compatibility snapshot'),('AI-Researcher','f9a6f8480860c193afff600eeffe3defcee8a978','reference'),('AgentLaboratory','d9017d90e329112d2a80b7712f37ee9094d2cd27','reference'),('AI-Scientist','1de1dbc1f4ee2c5f61e9c94348d55eb51d7fa2eb','reference'),('gpt-researcher','5d84d2f5553e70a2765a8ff3a0d2672d60437ce8','reference'),('deer-flow','917fe595fcfc2d5a30e7e55deed1bdb950785fc2','reference'),('sciagent','ece5fdfc9c62601883e21dc6e29939d38052e00f','reference'),('autoresearch','228791fb499afffb54b46200aca536f79142f117','reference'),('Academic-Paper-Skills','d67bf46aa3a0176847a2749ce84e99d556021f20','adapted skill'),('latex-arxiv-SKILL','349ce88a0797422911a4ce58ed335842e9b87e15','adapted skill'),('OpenScholar','0e9b8fb912273d3dae39e593da86e4f6d3bf8de1','reference'),('DeepScientist','b36624417f0c6b8238ec02db37b94d6db2faa5b0','reference')]
GATES = ('safety','ethics','license','data','evaluator','resource','evidence')

def d(root, n):
    p = root / '.howhow' / n
    p.mkdir(parents=True, exist_ok=True)
    return p

def rec(root, n, value, identifier):
    value = dict(value)
    value.update(schema_version=1, id=identifier, created_at=now())
    value['record_sha256'] = sha256_bytes(canonical(value))
    path = d(root, n) / (identifier + '.json')
    if path.exists():
        raise SystemExit('immutable record already exists: ' + identifier)
    atomic_json(path, value)
    append_event(root, n + '.recorded', {'id': identifier})
    return value

def opinion_state(root):
    path = root / 'OPINION.md'
    return 'MISSING' if not path.exists() else ('EMPTY' if path.stat().st_size == 0 else 'PRESENT')

def init_vnext(root):
    (root / 'OPINION.md').write_bytes(b'')
    modes = {
        'wanshuiyin ARIS': ('PINNED_REVIEWED', 'ADAPTED', True),
        'Randall ARIS': ('PINNED_REVIEWED', 'ADAPTER_DISABLED', False),
        'AI-Researcher': ('REFERENCE_REVIEWED', 'REFERENCE_ONLY', False),
        'AgentLaboratory': ('REFERENCE_REVIEWED', 'REFERENCE_ONLY', False),
        'AI-Scientist': ('RESTRICTED_REVIEW', 'RESTRICTED', False),
        'gpt-researcher': ('REFERENCE_REVIEWED', 'ADAPTER_DISABLED', False),
        'deer-flow': ('UNVERIFIED', 'ADAPTER_DISABLED', False),
        'sciagent': ('UNVERIFIED', 'REFERENCE_ONLY', False),
        'autoresearch': ('REFERENCE_REVIEWED', 'ADAPTED', True),
        'Academic-Paper-Skills': ('PINNED_REVIEWED', 'ADAPTED', True),
        'latex-arxiv-SKILL': ('PINNED_REVIEWED', 'ADAPTED', True),
        'OpenScholar': ('REFERENCE_REVIEWED', 'REFERENCE_ONLY', False),
        'DeepScientist': ('RESTRICTED_REVIEW', 'RESTRICTED', False),
    }
    contracts = {
        'wanshuiyin ARIS': ('reviewed upstream workflow inputs', 'bounded workflow plan and review gates', 'no execution or code import'),
        'Randall ARIS': ('pinned compatibility comparison', 'comparison notes only', 'older fork; adapter disabled'),
        'AI-Researcher': ('research task and evidence plan', 'reference workflow concepts', 'reference-only; no calls'),
        'AgentLaboratory': ('agent workflow stages', 'reference stage mapping', 'reference-only; no calls'),
        'AI-Scientist': ('experiment lifecycle shape', 'restricted lifecycle notes', 'restricted review; no execution'),
        'gpt-researcher': ('bounded query, limit, offline flag', 'provisional candidate metadata contract', 'adapter request only; live false'),
        'deer-flow': ('orchestration concepts', 'disabled execution export contract with exact pin', 'disabled; no calls; no implicit dependencies'),
        'sciagent': ('literature workflow concepts', 'reference workflow notes', 'reference-only; no calls'),
        'autoresearch': ('baseline-first clean-room protocol: one declared change, fixed objective, ledger, bounded stop', 'tested protocol contract', 'protocol only; no git reset, no infinite loop, no live adapter'),
        'Academic-Paper-Skills': ('paper structure, figures/tables provenance, and evidence checklist', 'D2 artifact manifest and conformance checks', 'adapted skill; immutable context only; no invented metrics'),
        'latex-arxiv-SKILL': ('approved plan, typed issue execution contract, deterministic compile and source-package QA', 'D2 compile/provenance/citation-preserving workflow', 'adapted skill; MIT notice and IEEEtran LPPL boundaries preserved; no submission'),
        'OpenScholar': ('literature synthesis concepts', 'reference synthesis notes', 'reference-only; no calls'),
        'DeepScientist': ('research planning concepts', 'restricted planning notes', 'restricted review; no execution'),
    }
    entries = [{'name': n, 'sha': s, 'license_status': modes[n][0], 'use_mode': modes[n][1], 'enabled': modes[n][2], 'howhow_contract': contracts[n][0], 'artifact': contracts[n][1], 'limitations': contracts[n][2], 'fixture_provenance': 'Phase A deterministic fixture; supplied approval pin', 'conformance_test': 'exact repository, SHA, license, mode, and live boundary', 'live_status': 'NOT_CALLED'} for n, s, _ in REPOS]
    for entry in entries:
        if entry['name'] == 'Academic-Paper-Skills':
            entry.update({'adaptation': 'HowHow D1/D2 content, figure/table, and review-contract translation; no copied code or substantial text', 'inspected_upstream_files': ['paper-writing skill/index', 'paper-policy/checklist materials', 'paper-figures-tables methods'], 'upstream_pin': 'd67bf46aa3a0176847a2749ce84e99d556021f20', 'translated_contract': 'paper context in; anchored sections and provenance manifests out; never invent evidence or metrics'})
        if entry['name'] == 'latex-arxiv-SKILL':
            entry.update({'adaptation': 'HowHow D2 clean-room compile, citation-preserving refinement, typed issue execution, and package-QA translation; no copied code', 'inspected_upstream_files': ['latex build workflow', 'citation and source-package checks'], 'upstream_pin': '349ce88a0797422911a4ce58ed335842e9b87e15', 'translated_contract': 'approved plan before prose; deterministic compile and extracted archive QA; no venue submission; MIT/IEEEtran boundaries preserved'})
    # E1 contract details are generated from the same pinned repository list and
    # retained in the project manifest; generation never inspects or mutates a checkout.
    from .adapters import contract
    for entry in entries:
        entry['e1_contract'] = contract(entry['name'])
    value = {'schema_version': 2, 'lineage': 'wanshuiyin ARIS is current upstream authority; Randall ARIS is an older fork/compatibility snapshot', 'integrations': entries}
    atomic_json(root / '.howhow/integration-manifest.json', value)

def capabilities(root):
    manifest = root / '.howhow/integration-manifest.json'
    entries = json.loads(manifest.read_text(encoding='utf-8'))['integrations'] if manifest.exists() else []
    from .adapters import _checkout_candidates
    cards = []
    for item in entries:
        e1 = item.get('e1_contract', {})
        installed = bool(_checkout_candidates(root, item['name']))
        available = installed and item.get('enabled', False) and item.get('use_mode') == 'ADAPTED'
        guidance = ('Installed and enabled: bounded adapter contract is available; it is still provisional.' if available else
                    'Contract is inspectable only; install the exact pinned checkout before treating it as available.' if not installed else
                    'Checkout is present but not enabled for live use; review its license and conformance first.')
        cards.append({'id': 'integration-' + safe_id(item['name'].lower().replace(' ', '-').replace('_', '-')), 'name': item['name'], 'status': item.get('use_mode', 'REFERENCE_ONLY'), 'installed': installed, 'available': available, 'enabled': item.get('enabled', False), 'live': item.get('live_status') == 'CALLED', 'sources': [item['name']], 'license_status': item['license_status'], 'sha': item['sha'], 'live_status': item.get('live_status', 'NOT_CALLED'), 'operations': e1.get('operations', []), 'restrictions': e1.get('restrictions', []), 'recommended_use': item.get('artifact', 'inspect the bounded contract'), 'guidance': guidance, 'limitations': item.get('limitations', 'No live adapter or execution is claimed')})
    return cards

def capability_list(root): return {'capabilities': capabilities(root), 'opinion': opinion_state(root)}
def capability_inspect(root, identifier):
    for item in capabilities(root):
        if item['id'] == identifier: return item
    raise SystemExit('unknown capability: ' + identifier)

def _require(condition, message):
    if not condition: raise SystemExit(message)

def brief_propose(root, title, mode='Hybrid'):
    _require(isinstance(title, str) and title, 'brief title is required')
    _require(mode in ('Manual', 'Hybrid', 'Auto'), 'mode must be Manual, Hybrid, or Auto')
    return rec(root, 'briefs', {'title': title, 'mode': mode, 'status': 'PROPOSED', 'steps': ['review capabilities and sources', 'choose a bounded idea', 'confirm target and execution', 'audit claims before human review']}, 'brief-' + str(len(list(d(root, 'briefs').glob('*.json'))) + 1))

def brief_show(root): return [json.loads(p.read_text()) for p in sorted(d(root, 'briefs').glob('*.json'))]
def brief_confirm(root, identifier):
    safe_id(identifier)
    original = json.loads((d(root, 'briefs') / (identifier + '.json')).read_text())
    _require(original.get('status') == 'PROPOSED', 'only a proposed brief can be confirmed')
    revision = 'brief-' + str(len(list(d(root, 'briefs').glob('*.json'))) + 1) + '-rev-' + str(len(list(d(root, 'briefs').glob('*.json'))) + 1)
    return rec(root, 'briefs', {k: v for k, v in original.items() if k not in {'schema_version','id','created_at','record_sha256'}} | {'status': 'CONFIRMED', 'confirmed_at': now(), 'revision_of': identifier}, revision)

def idea_add(root, value):
    _require(isinstance(value, dict), 'idea must be an object')
    identifier = safe_id(value.get('id', ''))
    _require(all(isinstance(value.get(k), str) and value[k] for k in ('title','question','evidence_plan')), 'idea requires id, title, question, evidence_plan')
    gates = value.get('gates')
    _require(isinstance(gates, dict) and all(isinstance(gates.get(k), bool) for k in GATES), 'idea gates require boolean safety, ethics, license, data, evaluator, resource, evidence')
    bad = [k for k in GATES if gates[k] is not True]
    return rec(root, 'ideas', {'title': value['title'], 'question': value['question'], 'evidence_plan': value['evidence_plan'], 'gates': gates, 'eligibility': 'REJECTED' if bad else 'ELIGIBLE', 'rejection_reasons': bad}, identifier)

def idea_rank(root):
    xs = [json.loads(p.read_text()) for p in sorted(d(root, 'ideas').glob('*.json'))]
    good = [x for x in xs if x.get('eligibility') == 'ELIGIBLE']
    _require(3 <= len(good) <= 5, 'ranking requires 3-5 valid candidates')
    items = [{'id': x['id'], 'rank': i, 'score': len(x['evidence_plan']), 'recommendation': i == 1} for i, x in enumerate(sorted(good, key=lambda x: (-len(x['evidence_plan']), x['id'])), 1)]
    return rec(root, 'rankings', {'items': items, 'rejected': [{'id': x['id'], 'reasons': x['rejection_reasons']} for x in xs if x.get('eligibility') != 'ELIGIBLE']}, 'ranking-' + str(len(list(d(root, 'rankings').glob('*.json'))) + 1))

def idea_select(root, identifier):
    rankings = sorted(d(root, 'rankings').glob('*.json'))
    _require(rankings, 'rank ideas before selection')
    _require(identifier in {x['id'] for x in json.loads(rankings[-1].read_text())['items']}, 'idea is not eligible or not ranked')
    return rec(root, 'selections', {'idea_id': identifier, 'user_selected': True, 'status': 'SELECTED'}, 'selection-' + str(len(list(d(root, 'selections').glob('*.json'))) + 1))

def _selected(root, idea_id):
    return any(json.loads(p.read_text()).get('idea_id') == idea_id and json.loads(p.read_text()).get('status') == 'SELECTED' for p in d(root, 'selections').glob('*.json'))

def target_propose(root, idea_id, words=0, pages=0, figures=0, tables=0, rationale='', argument_skeleton=None):
    _require(_selected(root, idea_id), 'target requires a selected ranked idea')
    _require(argument_skeleton is None or isinstance(argument_skeleton, (dict, list)), 'argument_skeleton must be an object or array')
    return rec(root, 'targets', {'idea_id': idea_id, 'suggested_words': words, 'suggested_pages': pages, 'suggested_figures': figures, 'suggested_tables': tables, 'rationale': rationale, 'venue_constraints': {}, 'argument_skeleton': argument_skeleton or [], 'user_decision': 'PENDING', 'status': 'PROPOSED'}, 'target-' + str(len(list(d(root, 'targets').glob('*.json'))) + 1))

def target_confirm(root, identifier, decision):
    safe_id(identifier)
    _require(decision == 'ACCEPT', 'target decision must be ACCEPT')
    original = json.loads((d(root, 'targets') / (identifier + '.json')).read_text())
    _require(original.get('status') == 'PROPOSED', 'only a proposed target can be confirmed')
    _require(_selected(root, original.get('idea_id')), 'target requires a selected ranked idea')
    number = len(list(d(root, 'targets').glob('*.json'))) + 1
    return rec(root, 'targets', {k: v for k, v in original.items() if k not in {'schema_version','id','created_at','record_sha256'}} | {'user_decision': decision, 'status': 'CONFIRMED', 'confirmed_at': now(), 'revision_of': identifier}, 'target-' + str(number) + '-rev-' + str(number))

def _valid_claim(value):
    _require(isinstance(value, dict), 'claim must be an object')
    _require(all(isinstance(value.get(k), str) and value[k] for k in ('id','section','paragraph','uncertainty')), 'claim requires id, section, paragraph, uncertainty')
    _require(value.get('type') in {'EXTERNAL','EMPIRICAL','INTERPRETIVE','HYPOTHESIS','LIMITATION','OPINION'}, 'invalid claim type')
    for key in ('supports','contradicts','source_ids','run_ids'):
        if key in value: _require(isinstance(value[key], list) and all(isinstance(x, str) for x in value[key]), key + ' must be a list of strings')

def claim_add(root, value):
    _valid_claim(value)
    return rec(root, 'claims', value, safe_id(value['id']))

def _records(root, folder): return {p.stem: json.loads(p.read_text()) for p in d(root, folder).glob('*.json')}
def _intact(record, identifier):
    unsigned = dict(record); digest = unsigned.pop('record_sha256', None)
    return record.get('id') == identifier and digest == sha256_bytes(canonical(unsigned))

def vnext_audit(root):
    """Validate every persisted Phase A/B record without changing it."""
    issues = []
    manifest = root / '.howhow/integration-manifest.json'
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
            expected = {name: sha for name, sha, _ in REPOS}
            entries = data.get('integrations', [])
            if len(entries) != len(REPOS) or len({item.get('name') for item in entries}) != len(entries): issues.append('integration manifest must contain exactly one entry per pinned repository')
            if {item.get('name') for item in entries} != set(expected): issues.append('integration manifest repository names do not match REPOS')
            for item in entries:
                name = item.get('name')
                if item.get('sha') != expected.get(name) or not isinstance(item.get('sha'), str) or len(item['sha']) != 40: issues.append(str(name) + ': invalid repository pin')
                if not isinstance(item.get('license_status'), str) or item.get('license_status') not in {'PINNED_REVIEWED','REFERENCE_REVIEWED','RESTRICTED_REVIEW','UNVERIFIED'}: issues.append(str(name) + ': invalid license status')
                if item.get('use_mode') not in {'ADAPTED','ADAPTER_DISABLED','REFERENCE_ONLY','RESTRICTED','BLOCKED'} or item.get('enabled') is not (item.get('use_mode') == 'ADAPTED'): issues.append(str(name) + ': invalid mode/enabled state')
                if not item.get('howhow_contract') or not item.get('artifact') or not item.get('limitations'): issues.append(str(name) + ': incomplete concrete contract')
                if item.get('live_status') != 'NOT_CALLED': issues.append(str(name) + ': live boundary violated')
            duplicate = root / 'integrations-manifest.json'
            if duplicate.exists(): issues.append('duplicate root integration manifest is forbidden; use .howhow/integration-manifest.json')
        except (OSError, ValueError, TypeError):
            issues.append('integration manifest unreadable')
    for folder in ('briefs', 'ideas', 'rankings', 'selections', 'targets'):
        for path in d(root, folder).glob('*.json'):
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                if path.stem != record.get('id') or not _intact(record, path.stem): issues.append(path.name + ': immutable hash or filename/id mismatch')
            except (OSError, ValueError, TypeError): issues.append(path.name + ': unreadable record')
    for path in d(root, 'briefs').glob('*.json'):
        record = json.loads(path.read_text())
        if not isinstance(record.get('title'), str) or not record.get('title') or record.get('mode') not in ('Manual', 'Hybrid', 'Auto') or record.get('status') not in ('PROPOSED', 'CONFIRMED'):
            issues.append(path.name + ': invalid research brief')
    for path in d(root, 'ideas').glob('*.json'):
        try: idea_add_validation(json.loads(path.read_text()))
        except SystemExit as exc: issues.append(path.name + ': ' + str(exc))
    claims = claim_audit(root)
    issues.extend(claims['issues'])
    from .literature import audit as literature_audit
    issues.extend('literature: ' + issue for issue in literature_audit(root)['issues'])
    from .experiment_v2 import experiment_audit
    issues.extend('experiment-v2: ' + issue for issue in experiment_audit(root)['issues'])
    return {'passed': not issues, 'issues': issues}

def idea_add_validation(value):
    _require(isinstance(value, dict), 'idea must be an object')
    _require(isinstance(value.get('title'), str) and value['title'] and isinstance(value.get('question'), str) and value['question'] and isinstance(value.get('evidence_plan'), str) and value['evidence_plan'], 'invalid idea fields')
    gates = value.get('gates')
    _require(isinstance(gates, dict) and all(isinstance(gates.get(k), bool) for k in GATES), 'invalid idea gates')

def claim_audit(root):
    claims = list(_records(root, 'claims').values()); ids = {x['id'] for x in claims}; bad = []
    sources = _records(root, 'sources/records')
    runs = _records(root, 'experiments')
    for claim in claims:
        try: _valid_claim(claim)
        except SystemExit as exc: bad.append(claim.get('id', '?') + ': ' + str(exc)); continue
        for linked in claim.get('supports', []) + claim.get('contradicts', []):
            if linked not in ids: bad.append(claim['id'] + ': unknown link ' + linked)
        for source_id in claim.get('source_ids', []):
            source = sources.get(source_id)
            if not source: bad.append(claim['id'] + ': unknown source_id ' + source_id)
            elif source.get('sha256') != sha256_file(root / '.howhow/sources/raw' / source_id / 'payload') if (root / '.howhow/sources/raw' / source_id / 'payload').exists() else True: bad.append(claim['id'] + ': source integrity failed ' + source_id)
        for run_id in claim.get('run_ids', []):
            run = runs.get(run_id)
            if not run: bad.append(claim['id'] + ': unknown run_id ' + run_id)
            elif not _intact(run, run_id): bad.append(claim['id'] + ': experiment integrity failed ' + run_id)
        if claim.get('type') == 'OPINION' and claim.get('evidence'): bad.append(claim['id'] + ': opinion cannot be evidence')
    return {'passed': not bad, 'issues': bad, 'human_scientific_review': 'SEPARATE', 'claim_count': len(claims)}
