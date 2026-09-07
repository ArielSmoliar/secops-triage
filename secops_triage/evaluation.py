"""Host-only, reviewer-mediated evaluation. Never semantic auto-grading or an agent tool."""
import argparse
import json
from pathlib import Path

from .contracts import Rejected, bounded, canonical, exact, sha
from .investigation import assess
from .store import Store


def snapshot(store, run_id, token, case_id):
    """Read verified current artifacts; expected answers never enter agent inputs."""
    from .evaluation_cases import get_expectations
    rubric = get_expectations(case_id)
    with store._locked() as db:
        row = store._owner(db, run_id, token)
        store._current(db, row)
        bundle = store._load(row)
        packet = store._packet(db, row)
        if row['snapshot'] != rubric['bundle_sha256']:
            raise Rejected('evaluation fixture mismatch')
        evidence = [store._get(run_id, item['hash']) for item in packet['evidence']]
    policy = assess(bundle, evidence)
    value = {'schema_version': 1, 'case_id': case_id, 'rubric': rubric,
             'evaluator_sha256': sha(Path(__file__).read_bytes()),
             'packet': packet, 'evidence': evidence, 'policy': policy,
             'raw_model_assessment': packet.get('agent_assessment')}
    return dict(value, source_hash=sha(canonical(value)))


def review_template(source):
    raw = source['raw_model_assessment']
    return {'source_hash': source['source_hash'], 'reviewer': '', 'reviewer_kind': '',
            'all_material_claims_split': False,
            'findings': [{'index': i, 'claims': [{'start': 0, 'end': len(f['summary']),
                          'verdict': 'unreviewed', 'rationale': ''}]}
                         for i, f in enumerate(raw['findings'] if raw else [])],
            'requirements': [{'id': f['id'], 'status': 'unreviewed', 'finding_indices': [], 'rationale': ''}
                             for f in source['rubric']['facts'] + source['rubric']['unknowns']]}


def score(source, review):
    """Check review completeness and compute separate dimensions, not entailment.

    Support and omission labels are explicit reviewer assertions. The original
    summaries and their citations remain unchanged in the bound source artifact.
    """
    if sha(canonical({k: v for k, v in source.items() if k != 'source_hash'})) != source['source_hash']:
        raise Rejected('evaluation source changed')
    exact(review, ('source_hash', 'reviewer', 'reviewer_kind', 'all_material_claims_split', 'findings', 'requirements'))
    if review['source_hash'] != source['source_hash']:
        raise Rejected('review targets changed evaluation source')
    if type(review['all_material_claims_split']) is not bool:
        raise Rejected('claim completeness attestation must be boolean')
    if review['reviewer_kind'] not in ('', 'human', 'ai') or type(review['reviewer']) is not str:
        raise Rejected('invalid reviewer identity')
    if review['reviewer']:
        bounded(review['reviewer'], 200)
    raw = source['raw_model_assessment']
    findings = raw['findings'] if raw else []
    if type(review['findings']) is not list or len(review['findings']) != len(findings):
        raise Rejected('every raw finding requires review')
    counts = dict.fromkeys(('supported', 'unsupported', 'unverifiable', 'unreviewed'), 0)
    reviewed_findings = []
    for index, (finding, annotation) in enumerate(zip(findings, review['findings'])):
        exact(annotation, ('index', 'claims'))
        if type(annotation['index']) is not int or annotation['index'] != index:
            raise Rejected('finding order changed')
        claims = annotation['claims']
        if type(claims) is not list or not 1 <= len(claims) <= 100:
            raise Rejected('invalid claim count')
        summary = finding['summary']
        position = 0
        verdicts = []
        for claim in claims:
            exact(claim, ('start', 'end', 'verdict', 'rationale'))
            start, end = claim['start'], claim['end']
            if (type(start) is not int or type(end) is not int or
                    not position <= start < end <= len(summary) or summary[position:start].strip() or
                    not summary[start:end].strip()):
                raise Rejected('claim spans must cover the original finding without overlap')
            verdict = claim['verdict']
            if type(verdict) is not str or verdict not in counts:
                raise Rejected('invalid support verdict')
            if type(claim['rationale']) is not str:
                raise Rejected('invalid review rationale')
            if verdict != 'unreviewed':
                bounded(claim['rationale'])
            counts[verdict] += 1
            verdicts.append(verdict)
            position = end
        if summary[position:].strip():
            raise Rejected('unreviewed text omitted from finding')
        reviewed_findings.append(all(v == 'supported' for v in verdicts))
    requirements = source['rubric']['facts'] + source['rubric']['unknowns']
    if type(review['requirements']) is not list or len(review['requirements']) != len(requirements):
        raise Rejected('every rubric requirement needs an omission review')
    omissions, pending = [], []
    for expected, item in zip(requirements, review['requirements']):
        exact(item, ('id', 'status', 'finding_indices', 'rationale'))
        if item['id'] != expected['id'] or item['status'] not in ('present', 'omitted', 'unreviewed'):
            raise Rejected('invalid requirement review')
        indices = item['finding_indices']
        if type(indices) is not list or any(type(i) is not int or not 0 <= i < len(findings) for i in indices) or len(set(indices)) != len(indices):
            raise Rejected('invalid requirement finding references')
        if item['status'] == 'present':
            if not indices or not all(reviewed_findings[i] for i in indices):
                raise Rejected('present requirement must map to supported reviewed findings')
        elif indices:
            raise Rejected('only present requirements may reference findings')
        if type(item['rationale']) is not str:
            raise Rejected('invalid omission rationale')
        if item['status'] != 'unreviewed':
            bounded(item['rationale'])
        if item['status'] == 'omitted':
            omissions.append(item['id'])
        elif item['status'] == 'unreviewed':
            pending.append(item['id'])
    has_judgments = counts['supported'] + counts['unsupported'] + counts['unverifiable'] > 0 or len(pending) != len(requirements)
    if has_judgments and (not review['reviewer'].strip() or not review['reviewer_kind']):
        raise Rejected('review judgments require attributed reviewer')
    packet, policy, rubric = source['packet'], source['policy'], source['rubric']
    expected = rubric['recommendation']
    model_matches = None if raw is None else raw['recommendation'] == (expected or 'needs_review')
    policy_matches = policy['recommendation'] == expected and policy['investigation_status'] == rubric['investigation_status']
    final_matches = packet['recommendation'] == expected and packet['investigation_status'] == rubric['investigation_status']
    disagreement = None if raw is None else raw['recommendation'] != (policy['recommendation'] or 'needs_review')
    if raw is None:
        outcome = 'not_evaluated'
    elif not model_matches or not policy_matches or not final_matches or counts['unsupported'] or counts['unverifiable'] or omissions:
        outcome = 'fail'
    elif counts['unreviewed'] or pending or not review['all_material_claims_split']:
        outcome = 'pending_review'
    else:
        outcome = 'pass'
    return {'schema_version': 1, 'source_hash': source['source_hash'], 'review_hash': sha(canonical(review)),
            'outcome': outcome, 'raw_model_recommendation': raw['recommendation'] if raw else None,
            'raw_model_matches_expected': model_matches, 'deterministic_matches_expected': policy_matches,
            'final_packet_matches_expected': final_matches, 'reconciliation_disagreement': disagreement,
            'claim_support': counts, 'omitted_requirements': omissions, 'unreviewed_requirements': pending,
            'reviewer': review['reviewer'], 'reviewer_kind': review['reviewer_kind'],
            'execution': packet['execution'], 'case_status': rubric['status'],
            'campaign_acceptance': False,
            'limits': 'Reviewer assertions, not automated semantic entailment; draft case and offline runs do not satisfy live or analyst acceptance.'}


def main():
    from .live import write_private
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'score'))
    parser.add_argument('--run', required=True, type=Path, help='Existing private prepared run directory')
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True, type=Path, help='New private evaluation directory')
    parser.add_argument('--review', type=Path, help='Completed review JSON for score')
    args = parser.parse_args()
    try:
        run = args.run.absolute(); Store._safe(run)
        # Read capability only internally; never copy it into evaluation artifacts.
        owner = json.loads((run / 'owner.json').read_text())
        source = snapshot(Store(run / 'store'), owner['run_id'], owner['token'], args.case)
        if args.command == 'score':
            if args.review is None or args.review.stat().st_size > 500000:
                raise Rejected('bounded review file required')
            from .__main__ import unique_object
            review = json.loads(args.review.read_text(), object_pairs_hook=unique_object)
        else:
            review = review_template(source)
        result = score(source, review)
        output = args.output.absolute(); Store._safe(output)
        output.mkdir(parents=True, mode=0o700, exist_ok=False)
        write_private(output / 'source.json', source)
        write_private(output / 'review.json', review)
        write_private(output / 'score.json', result)
        print(json.dumps({'output': str(output), 'outcome': result['outcome'], 'campaign_acceptance': False}))
    except (Rejected, ValueError, OSError, KeyError, TypeError):
        parser.exit(2, 'Evaluation stopped; verify current run, case identity and review bindings.\n')


if __name__ == '__main__':
    main()
