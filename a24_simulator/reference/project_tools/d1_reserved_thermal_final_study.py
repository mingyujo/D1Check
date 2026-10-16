"""Frozen rule-only 192-condition evaluation; cumulative owner/receipt budget."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import json
import os
import subprocess
import time
from tools import d1_reserved_thermal_numeric_study as n
from tools import d1_triton_rules as triton

s = n.s
LOCAL = s.LOCAL/'final_rule_only_v1'
BUNDLE = s.BUNDLE/'final_rule_only'
POLICIES = list(triton.CONFIGS)+['BAND_HEFT_WHOLE_REQUEST_ADAPT_V1', 'SHARED_EFT',
    'ENERGY_AP_REQUEST_V1', 'ARRIVED_QUEUE_J_PEAK_AREA_V1', 'EFT_REFERENCE', n.r2.PUBLIC_POLICY]


def sources():
    return dict(s.source_hashes(), **n.sources(), **{name:s.digest(s.ROOT/name) for name in
        ('tools/d1_triton_rules.py','tools/d1_reserved_thermal_final_study.py')})


def prepare():
    s.check(); n.register()
    review_path=n.BUNDLE/'rule_only_review.json'; review=s.read(review_path)
    if (review['decision']!='PROCEED_RULE_ONLY' or review['training_allowed']
        or review['runtime_hashes']!=n.sources()
        or review['numeric_verification_sha256']!=s.digest(n.BUNDLE/'verification.json')
        or review['summary_sha256']!=s.digest(n.BUNDLE/'summary.json')
        or review['report_sha256']!=s.digest(n.BUNDLE/'RULE_ONLY_REVIEW.md')):
        raise ValueError('rule-only review drift')
    path=LOCAL/'registration.json'
    if path.exists(): registration=s.read(path)
    else:
        if (s.LOCAL/'owner.json').exists() or s.consumption()['environment_starts']!=129:
            raise ValueError('final registration requires existing cumulative129 and no owner')
        seeds=review['final_scope']['seeds']
        search=subprocess.run(['rg','-l',r'\b6108800(0[1-9]|1[0-6])\b','docs','output',
            '--glob','*.json','--glob','*.csv','--glob','*.jsonl',
            '--glob','!**/reserved_thermal_01/**','--glob','!**/reserved_thermal_20261008_v1/**'],
            capture_output=True,text=True,encoding='utf8')
        if search.returncode!=1: raise ValueError('prior registered seed collision or inventory error: '+search.stdout+search.stderr)
        inputs,_,_,_=n.reuse()
        inputs=dict(initial=inputs['initial'], workloads=[dict(seed=seed,family=family,
            tickets=s.existing.old.workload(family,seed)) for seed in seeds for family in s.existing.old.FAMILIES])
        s.immutable(LOCAL/'inputs.json',inputs);s.write(BUNDLE/'inputs.json',inputs)
        registration=dict(version='reserved-thermal-final-rule-only-v1',utc=s.utc(),
            head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
            source_hashes=sources(),review_sha256=s.digest(review_path),
            inputs_sha256=s.digest(LOCAL/'inputs.json'),seeds=seeds,seed_collision_files=[],
            seed_collision_scope='prior docs/output uncompressed JSON/CSV/JSONL; own campaign excluded',
            policies=POLICIES,contexts=list(s.existing.old.SCENARIOS),conditions=192,logical_rows=2112,
            baseline_consumption=s.consumption(),maximum_environment_starts=2128,
            wall_seconds=3600,save_reserve_seconds=300,training_episodes=0,device_commands=0,
            representative=dict(seed=seeds[0],families=['queue','sustained'],context='mean'),
            service_primary_families=['low','sustained'],realization_seed=201,
            coefficient_fitting=False,strict_supported=False,experiment_ready=False)
        s.immutable(path,registration);s.journal('final_rule_registration',sha256=s.digest(path))
    if (registration['source_hashes']!=sources() or registration['policies']!=POLICIES
        or registration['review_sha256']!=s.digest(review_path)
        or registration['inputs_sha256']!=s.digest(LOCAL/'inputs.json')):
        raise ValueError('final frozen registration drift')
    s.write(BUNDLE/'registration.json',registration)
    return registration


def begin(registration,name,planned):
    s.check()
    if sources()!=registration['source_hashes']: raise ValueError('final source drift')
    owner=s.read(s.LOCAL/'owner.json')
    if owner['pid']!=os.getpid(): raise ValueError('final owner mismatch')
    used=s.consumption()['environment_starts']
    if used>=20000 or used-registration['baseline_consumption']['environment_starts']>=2128:
        raise RuntimeError('final/cumulative environment budget exhausted')
    clock=LOCAL/'clock.json'
    if not clock.exists(): s.immutable(clock,dict(start_utc=s.utc()))
    if (datetime.now(timezone.utc)-datetime.fromisoformat(s.read(clock)['start_utc'])).total_seconds()>=3300:
        raise TimeoutError('final save reserve; no reset')
    number=used+1
    s.journal('start',kind='evaluation',name=name,number=number,planned_requests=planned)
    return number


def run():
    registration=prepare(); inputs=s.read(LOCAL/'inputs.json')
    frozen,_=s.rule.P.inputs(s.rule.P.BUNDLE)
    binding=dict(registration_sha256=s.digest(LOCAL/'registration.json'),source_hashes=sources())
    rows=[]
    with s.owner():
        for work in inputs['workloads']:
            for context in registration['contexts']:
                for policy in POLICIES:
                    index=len(rows);name=f"final_rule/{work['seed']}/{work['family']}/{context}/{policy}"
                    path=LOCAL/f'items/{index:04d}.json.gz'
                    if path.exists(): item=n.read_item(path,binding,name,work['tickets'])
                    else:
                        number=begin(registration,name,len(work['tickets']));began=time.perf_counter()
                        try:
                            if policy==n.r2.PUBLIC_POLICY:
                                row,result,c,_=n.r2.simulate(frozen,inputs['initial'],work['tickets'],context,lambda:None)
                            else:
                                result,c=(triton.simulate(frozen,inputs['initial'],work['tickets'],context,policy)
                                    if policy in triton.CONFIGS else
                                    s.existing.rules.simulate(frozen,inputs['initial'],work['tickets'],context,policy))
                                row={}
                            s.existing.audit(result,work['tickets'])
                            common,curves=s.existing.metrics(result,c,inputs['initial'],frozen)
                            row.update(common,seed=work['seed'],family=work['family'],context=context,
                                policy=policy,scope='resource',environment='immediate_allow',origin='final_rule_only')
                            item=dict(identity=name,binding=binding,row=row,result=result,curves=curves,
                                records=getattr(c,'records',[]),numeric_events=getattr(c,'numeric_events',[]),
                                action_audit=getattr(c,'action_audit',[]),host_wall_s=time.perf_counter()-began)
                            path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp')
                            temp.write_bytes(gzip.compress(json.dumps(item,ensure_ascii=False,allow_nan=False).encode('utf8'),mtime=0))
                            temp.replace(path)
                            s.journal('completed',kind='evaluation',name=name,number=number,
                                item_sha256=s.digest(path),host_wall_s=item['host_wall_s'])
                        except BaseException as error:
                            s.journal('failed',kind='evaluation',name=name,number=number,error=repr(error));raise
                    rows.append(item['row'])
                    s.write(LOCAL/'progress.json',dict(completed_rows=len(rows),total=2112,consumption=s.consumption()))
                print(f'{len(rows)}/2112 {work["seed"]}/{work["family"]}/{context}',flush=True)
    s.existing.csv_write(BUNDLE/'results.csv',rows)
    receipt=dict(status='completed',utc=s.utc(),logical_rows=2112,conditions=192,policies=11,
        binding=binding,consumption=s.consumption(),training_episodes=0,device_commands=0)
    s.write(BUNDLE/'completion.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','run'))
    action=parser.parse_args().action
    result=prepare() if action=='prepare' else run()
    print(json.dumps(dict(status=result.get('status','registered'),conditions=192,logical_rows=2112,
                         consumption=s.consumption()),ensure_ascii=False,indent=2))
