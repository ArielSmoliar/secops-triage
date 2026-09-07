"""Draft campaign planning only. No dispatch, authorization, retries or acceptance."""
import argparse
import json
from pathlib import Path
import subprocess

from .agent_spend import CALLS, BUDGET_MICROUSD
from .contracts import IncidentBundle, REQUIRED, Rejected, canonical, sha
from .evaluation_cases import CASE_IDS, get_case, get_expectations
from .store import Store, engine_digest


def build_plan():
    from migration_proof.agent.openai_preflight import MODEL_ID, PRICE_CHECKED_ON
    root = Path(__file__).resolve().parents[1]
    cases = {}
    for case_id in CASE_IDS:
        value = get_case(case_id)
        bundle = IncidentBundle.from_dict(value)
        if not bundle.synthetic or len(bundle.alerts) != 1:
            raise Rejected('campaign case requires one synthetic alert')
        reads = 1 + len(bundle.entities) + len(REQUIRED[bundle.alerts[0].family]) + 1
        if reads > CALLS - 1:
            raise Rejected('case exceeds existing tool-call bound')
        rubric = get_expectations(case_id)
        digest = sha(canonical(value))
        if rubric['bundle_sha256'] != digest:
            raise Rejected('case rubric identity mismatch')
        cases[case_id] = {'family': bundle.alerts[0].family, 'fixture_sha256': digest,
                          'rubric_sha256': sha(canonical(rubric)), 'minimum_reads': reads,
                          'case_status': rubric['status'], 'owner_acceptance': 'pending'}
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True))
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, True
    source = {str(p.relative_to(root)): sha(p.read_bytes())
              for name in ('secops_triage', 'migration_proof') for p in sorted((root / name).rglob('*.py'))}
    source['uv.lock'] = sha((root / 'uv.lock').read_bytes())
    engine = engine_digest()
    slots = []
    # Keep the three hero acceptance attempts adjacent; no hidden diagnosis slots.
    order = [case_id for case_id in CASE_IDS if case_id != 'case-04'] + ['case-04'] * 3
    for index, case_id in enumerate(order, 1):
        slots.append({'slot_id': f'm2-{index:02d}', 'milestone': 'M2', 'case_id': case_id,
                      'purpose': 'hero_repeat' if index > len(CASE_IDS) else 'case_acceptance',
                      'mode': 'proposed_live', 'execution_engine_hash': engine,
                      'fixture_sha256': cases[case_id]['fixture_sha256'],
                      'requests_max': CALLS, 'tool_calls_max': CALLS - 1,
                      'wall_seconds_max': 120, 'ceiling_microusd': BUDGET_MICROUSD,
                      'authorization': 'not_issued', 'state': 'unexecuted', 'run_id': None})
    for index in range(1, 4):
        slots.append({'slot_id': f'm4-hero-{index}', 'milestone': 'M4', 'case_id': 'case-04',
                      'purpose': 'finished_ui_hero_rehearsal', 'mode': 'proposed_live',
                      'execution_engine_hash': None, 'build_binding': 'pending_finished_ui_build',
                      'fixture_sha256': cases['case-04']['fixture_sha256'],
                      'requests_max': CALLS, 'tool_calls_max': CALLS - 1,
                      'wall_seconds_max': 120, 'ceiling_microusd': BUDGET_MICROUSD,
                      'authorization': 'not_issued', 'state': 'unexecuted', 'run_id': None})
    for case_id in ('case-07', 'case-03'):
        previous = next(s['slot_id'] for s in slots if s['milestone'] == 'M2' and s['case_id'] == case_id)
        slots.append({'slot_id': 'm4-playback-' + case_id, 'milestone': 'M4', 'case_id': case_id,
                      'purpose': 'alternate_saved_walkthrough', 'mode': 'proposed_saved_playback',
                      'source_slot': previous, 'fixture_sha256': cases[case_id]['fixture_sha256'],
                      'requests_max': 0, 'tool_calls_max': 0, 'wall_seconds_max': None,
                      'ceiling_microusd': 0, 'authorization': 'not_applicable',
                      'state': 'unexecuted', 'run_id': None})
    plan = {'schema_version': 1, 'status': 'draft_not_authorized', 'ready_to_execute': False,
            'model': MODEL_ID, 'configured_price_checked_on': PRICE_CHECKED_ON.isoformat(),
            'pricing_reverified_by_planner': False, 'source_commit': commit, 'worktree_dirty': dirty,
            'engine_hash': engine, 'source_sha256': source, 'cases': cases, 'slots': slots,
            'totals': {stage: {'proposed_live_runs': sum(s['mode'] == 'proposed_live' for s in slots if s['milestone'] == stage),
                              'requests_max': sum(s['requests_max'] for s in slots if s['milestone'] == stage),
                              'ceiling_microusd': sum(s['ceiling_microusd'] for s in slots if s['milestone'] == stage)}
                       for stage in ('M2', 'M4')},
            'gates': ['Actual formative analyst session', 'Owner acceptance of all case rubrics',
                      'Fresh price/bounds verification', 'Explicit campaign spending authorization',
                      'Current execution-build verification; finished UI build for M4'],
            'stop_rules': ['Preserve every failed, stopped, incomplete and completed attempt.',
                           'Stop on unsupported material claims, unsafe close, scope or spending failure.',
                           'No automatic retries or diagnosis calls; revisions require new proposal and authority.',
                           'Never count saved playback as fresh inference or an M2 run as a finished-UI rehearsal.'],
            'accounting': 'All slots are unexecuted planning entries, not an execution ledger or grants. Per-run receipts and durable grant/result reconciliation must be implemented before campaign dispatch.'}
    return dict(plan, plan_hash=sha(canonical(plan)))


def write_plan(output):
    from .live import write_private
    plan = build_plan()
    output = Path(output).absolute(); Store._safe(output)
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    write_private(output / 'campaign-plan.json', plan)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New private planning directory')
    args = parser.parse_args()
    try:
        plan = write_plan(args.output)
        print(json.dumps({'output': str(args.output.absolute()), 'plan_hash': plan['plan_hash'],
                          'totals': plan['totals'], 'ready_to_execute': False}))
    except (OSError, ValueError, KeyError):
        parser.exit(2, 'Campaign planning stopped; verify fixtures and output directory.\n')


if __name__ == '__main__':
    main()
