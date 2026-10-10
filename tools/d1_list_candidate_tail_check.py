"""Audit finished requests, mask likelihoods, archives and cumulative budgets.

Reads completed evidence only; environment/learning/device starts are zero.
"""
import argparse
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import torch
from tools import d1_list_candidate_rl as core


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check(run):
    run=Path(run);reg=json.loads((run/'registration_effective.json').read_text(encoding='utf-8'))
    starts={};done={}
    for line in (run/'execution.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line);table=done if 'event' in row else starts
        if row['number'] in table:raise ValueError('duplicate consumption/completion')
        table[row['number']]=row
    if set(starts)!=set(done):raise ValueError('unaccounted/unfinished environment start')
    counts=dict(environments=len(starts),learning=sum(q['learning'] for q in starts.values()),
        planned=0,completed=0,unfinished=0,failed_native=0,physical_overlap_s=0.,
        controller_snapshots=0,on_policy_sampled_decisions=0,forced_decisions=0)
    phase=Counter(q['phase'] for q in starts.values())
    for name,count in phase.items():
        if count>reg['stage_caps'][name]:raise ValueError('stage cap exceeded')
    if counts['environments']>1536 or counts['learning']>416:raise ValueError('tranche cap exceeded')
    torch.set_num_threads(1)
    for number,start in starts.items():
        end=done[number]
        if end['status']!='completed':raise ValueError('failed native start remains')
        artifact=run/'items'/(start['identity']+'.json.gz')
        if sha(artifact)!=end['artifact_sha256']:raise ValueError('changed raw result')
        item=json.loads(gzip.decompress(artifact.read_bytes()));ledger=item['result']['ledger']
        if len(ledger)!=start['planned'] or len({q['id'] for q in ledger})!=len(ledger):raise ValueError('request loss/duplicate')
        counts['planned']+=len(ledger);completed=sum(q['status']=='succeeded' for q in ledger)
        counts['completed']+=completed;counts['unfinished']+=len(ledger)-completed
        if completed!=item['row']['completed'] or len(ledger)-completed!=item['row']['incomplete']:raise ValueError('completion denominator mismatch')
        lanes={'CPU':[],'GPU':[]}
        for q in ledger:
            if 'dispatch_ns' not in q:continue
            if q['backend'] not in lanes or q['task']=='detection' and q['backend']!='CPU':raise ValueError('unsupported backend')
            keys=('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')
            values=[q[k] for k in keys if k in q]
            if values!=sorted(values):raise ValueError('time/phase reversal')
            if q['status']=='succeeded':
                if len(values)!=6:raise ValueError('successful request missing phase')
                response=q['output_ready_ns'] if q['task']=='classification' else q['persist_complete_ns']
                if abs(q['response_ns']-(response-q['arrival_ns']))>1:raise ValueError('response confused with lane release')
                if q['late_success']!=(q['response_ns']>q['deadline_offset_ns']):raise ValueError('late success dropped')
            lanes[q['backend']].append(q)
        finish=lambda q:q.get('lane_available_ns',120e9)
        for jobs in lanes.values():
            jobs.sort(key=lambda q:q['dispatch_ns'])
            if any(finish(a)>b['dispatch_ns'] for a,b in zip(jobs,jobs[1:])):raise ValueError('occupied lane assigned twice')
        for a in lanes['CPU']:
            for b in lanes['GPU']:
                dt=min(finish(a),finish(b))-max(a['dispatch_ns'],b['dispatch_ns'])
                if dt>0:
                    if (a['task'],b['task'])!=('detection','classification'):raise ValueError('unverified parallel group')
                    counts['physical_overlap_s']+=dt/1e9
        statefile=run/'items'/(start['identity']+'.pt')
        if not end.get('controller_sha256'):continue
        if sha(statefile)!=end['controller_sha256']:raise ValueError('controller archive changed')
        saved=torch.load(statefile,map_location='cpu',weights_only=False)['controller']
        if saved['schema_id']!=start['schema_id']:raise ValueError('schema/variant provenance mismatch')
        for s in saved['snapshots']:
            counts['controller_snapshots']+=1
            mask=s['mask'];physical=s.get('physical_mask',mask)
            if not mask[s['chosen']] or (mask & ~physical).any():raise ValueError('selected forbidden action')
            if any(q['arrival_ns']>s['now_ns'] for q in s['public_queue']):raise ValueError('future request exposed')
            if s.get('physical_mask') is not None:
                if not mask[s['base']]:raise ValueError('physical L0 removed')
                if s['informative']!=(int(mask.sum())>1):raise ValueError('forced action treated as informative')
            if s.get('actor_eligible'):
                counts['on_policy_sampled_decisions']+=1
                if int(mask.sum())<=1 or s.get('logprob') is None:raise ValueError('forced/missing-likelihood actor sample')
            else:counts['forced_decisions']+=int(mask.sum())==1
    archives=[];optimizer_main=0
    for variant in ('current','tail'):
        for seed in (11,23,37):
            path=run/f'checkpoints/{variant}_seed{seed}_terminal64.pt'
            payload=torch.load(path,map_location='cpu',weights_only=False)
            if payload['accepted_episodes']!=64 or payload['update_count']!=8 or payload['pending_episodes']:
                raise ValueError('not an intact final64 learner')
            if not payload['optimizer']['state'] or payload['schema_id']!=reg['schemas'][variant]:raise ValueError('missing Adam/wrong variant')
            if payload['dependencies']['caller_contracts']['registration_sha256']!=core.digest(reg):raise ValueError('learner registration changed')
            if payload['cursor']!=dict(variant=variant,seed=seed,next_episode=64):raise ValueError('terminal cursor lost')
            optimizer_main+=payload['optimizer_steps']
            archives.append(dict(path=path.relative_to(run).as_posix(),sha256=sha(path),variant=variant,seed=seed,
                episodes=64,updates=8,optimizer_steps=payload['optimizer_steps'],schema_id=payload['schema_id'],Adam_nonempty=True,
                full_RNG_and_multipliers=True,partial_episodes=0))
    progress=json.loads((run/'progress.json').read_text(encoding='utf-8'))['consumption']
    if counts['environments']!=1404 or counts['learning']!=404:raise ValueError('registered final executed count mismatch')
    if progress['cumulative_environment_starts']!=7865+counts['environments'] or progress['cumulative_learning_starts']!=1045+counts['learning']:
        raise ValueError('cumulative consumption reset')
    if (run/'owner.lock').exists():raise ValueError('run still owned')
    result=dict(status='PASS',counts=counts,phase_counts=dict(phase),terminal_archives=archives,
        main_optimizer_steps=optimizer_main,resume_optimizer_steps=json.loads((run/'resume_verification.json').read_text())['actual_optimizer_steps'],
        cumulative=progress,verification_environment_learning_device_starts=0,
        scope='full arrival denominator and completed/unfinished statuses; physical scheduled overlap, not execution-only overlap',
        executed_registration_sha256=sha(run/'registration_effective.json'))
    (run/'final_artifact_verification.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();print(json.dumps(check(a.run),indent=2))
