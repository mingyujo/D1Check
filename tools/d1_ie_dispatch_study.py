"""Bounded source-pinned IE comparison; durable starts, cache reuse, no devices."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import subprocess
import time
from tools import d1_ie_dispatch as rule
from tools import d1_external_rules_study as audit

p = rule.p
ROOT = p.ROOT
BUNDLE = ROOT/'docs/results/ie_dispatch_01'
LOCAL = ROOT/'output/ie_dispatch_20261008_v1'
PREVIOUS = ROOT/'docs/results/reserved_thermal_01/final_rule_only'
OLD_LOCAL = ROOT/'output/reserved_thermal_20261008_v1'
BASES = ('SHARED_EFT', 'EFT_REFERENCE', 'BAND_HEFT_WHOLE_REQUEST_ADAPT_V1',
         'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1', 'ENERGY_AP_REQUEST_V1', 'ARRIVED_QUEUE_J_PEAK_AREA_V1')


def read(path): return json.loads(Path(path).read_text(encoding='utf8'))
def utc(): return datetime.now(timezone.utc).isoformat()
def head(): return subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
def write(path, obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf8',newline='\n') as stream:
        json.dump(obj,stream,ensure_ascii=False,allow_nan=False,indent=2); stream.write('\n')
        stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)


def sources():
    files=dict(audit.existing_sources())
    for name in ('tools/d1_external_rules.py','tools/d1_external_rules_study.py',
                 'tools/d1_ie_dispatch.py','tools/d1_ie_dispatch_study.py'):
        files[name]=p.digest(ROOT/name)
    return files


def entries(path):
    return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()] if path.exists() else []


def consumption():
    old=entries(OLD_LOCAL/'executions.jsonl');new=entries(LOCAL/'executions.jsonl')
    return dict(previous_starts=sum(r['event']=='start' for r in old),
        new_starts=sum(r['event']=='start' for r in new),
        cumulative_starts=sum(r['event']=='start' for r in old+new),
        new_failed_starts=sum(r['event']=='failed' for r in new),
        training_episodes=0, device_commands=0, ceiling=20000)


def journal(event, **fields):
    with (LOCAL/'executions.jsonl').open('a',encoding='utf8',newline='\n') as stream:
        stream.write(json.dumps(dict(utc=utc(),event=event,**fields),ensure_ascii=False,allow_nan=False)+'\n')
        stream.flush();os.fsync(stream.fileno())


def prepare():
    LOCAL.mkdir(parents=True,exist_ok=True)
    path=BUNDLE/'contract.json'
    if path.exists(): return check()
    if (OLD_LOCAL/'owner.json').exists() or (LOCAL/'owner.json').exists():
        raise RuntimeError('active/unresolved owner; do not touch running experiment')
    previous=read(PREVIOUS/'verification.json')
    for name in ('inputs.json','registration.json','results.csv'):
        if p.digest(PREVIOUS/name)!=previous['outputs'][name]: raise ValueError('old bundle drift: '+name)
    protected={name:p.digest(ROOT/name) for name in sources()}
    for name,sha in previous['source_hashes'].items():
        if p.digest(ROOT/name)!=sha: raise ValueError('old frozen source drift: '+name)
    users=[q for q in ROOT.iterdir() if q.is_file() and q.suffix.lower() in ('.html','.pdf')]
    users += [q for q in (ROOT/'.vscode').rglob('*') if q.is_file()]
    users += [q for folder in ROOT.glob('*_files') for q in folder.rglob('*') if q.is_file()]
    write(LOCAL/'protected_user_files.json',{q.relative_to(ROOT).as_posix():p.digest(q) for q in users})
    baseline=consumption()
    if baseline['new_starts'] or baseline['previous_starts']!=2241:
        raise ValueError('existing consumption must be preserved, not recreated')
    c=dict(version='ie-dispatch-pc-v1',id='IE-DISPATCH-PC-01',registered_utc=utc(),head=head(),dirty=True,
        source_hashes=protected,mapping_sha256=p.digest(BUNDLE/'mapping.md'),
        input_path=(PREVIOUS/'inputs.json').relative_to(ROOT).as_posix(),input_sha256=p.digest(PREVIOUS/'inputs.json'),
        prior_verification_path=(PREVIOUS/'verification.json').relative_to(ROOT).as_posix(),
        prior_verification_sha256=p.digest(PREVIOUS/'verification.json'),
        new_policies=list(rule.POLICIES),reused_policies=list(BASES),conditions=192,
        new_rows=576,reused_rows=1152,logical_rows=1728,maximum_new_environment_starts=600,
        baseline_consumption=baseline,whole_ceiling=20000,learning_ceiling_unchanged=6144,
        wall_seconds=3600,save_reserve_seconds=300,realization_seed=201,
        tuning_candidates=0,independent_holdout=False,
        scope='already seen 192 synthetic conditions; fixed rule comparison, not new unseen test',
        ect_objective='mean predicted end of all5 phases including actual lane ownership',
        spt_processing_time='minimum mean all5 time over supported backends',
        no_aging_override=True,no_deadline_drop=True,device_commands=0,training_episodes=0,
        physical_model_sha256=p.MODEL_SHA,initial_source_sha256=p.INITIAL_SHA,
        energy_window_s=[0,120],ap_window_s=[35,180],ap_safety_limit_c=None,
        primary_families=['low','sustained'],strict_supported=False,experiment_ready=False,
        representative=dict(seed=610880001,family='queue',context='mean'),
        smoke_first_rows=6,fixture_new_runs=6,unchanged_baseline_regressions=2,
        service='full denominator + urgent/normal failures + urgentP95 nonworsening; then J/AP',
        prior_budget_note='new diagnostics counted against remaining20000; old stage2/clock not reset; proposed RL run not started')
    write(path,c);write(LOCAL/'registration.json',c);write(LOCAL/'clock.json',dict(start_utc=utc()))
    return check()


def check():
    c=read(BUNDLE/'contract.json')
    if read(LOCAL/'registration.json')!=c: raise ValueError('registration drift')
    for name,sha in c['source_hashes'].items():
        if p.digest(ROOT/name)!=sha: raise ValueError('source drift: '+name)
    for name,key in [('mapping.md','mapping_sha256')]:
        if p.digest(BUNDLE/name)!=c[key]: raise ValueError('mapping drift')
    for name,key in [('input_path','input_sha256'),('prior_verification_path','prior_verification_sha256')]:
        if p.digest(ROOT/c[name])!=c[key]: raise ValueError('reference drift')
    used=consumption()
    if used['cumulative_starts']>20000 or used['new_starts']>600: raise ValueError('budget exceeded')
    return c


def begin(kind, identity):
    c=check();used=consumption()
    if used['cumulative_starts']>=20000 or used['new_starts']>=600: raise RuntimeError('start ceiling')
    start=datetime.fromisoformat(read(LOCAL/'clock.json')['start_utc'])
    if (datetime.now(timezone.utc)-start).total_seconds()>=3300: raise TimeoutError('last5min save reserve')
    if read(LOCAL/'owner.json')['pid']!=os.getpid(): raise RuntimeError('owner mismatch')
    number=used['new_starts']+1
    journal('start',number=number,cumulative_number=used['cumulative_starts']+1,kind=kind,identity=identity)
    return number


def conformance(result,tickets):
    audit.audit(result,tickets)
    by={q['id']:q for q in tickets};estimates=p.profile(p.inputs(p.BUNDLE)[0])
    for d in result['decisions']:
        if 'ordered_ids' not in d: continue
        qs=[by[i] for i in d['ordered_ids']]
        if any(q['arrival_ns']>d['now_ns'] for q in qs): raise ValueError('future queue')
        if qs!=sorted(qs,key=lambda q:rule.order_key(q,estimates,d['sequencing_rule'])):
            raise ValueError('sequencing mismatch')
        if d['candidates']:
            chosen=min(d['candidates'],key=lambda j:(j['end'],j['backend']!='CPU'))
            if chosen['backend']!=d['chosen_backend']: raise ValueError('ECT mismatch')
        if d['selected'] and d['selected']['request_id']!=d['head_request_id']:
            raise ValueError('head bypass')


def cache():
    c=check();verification=read(ROOT/c['prior_verification_path']);found={};hashes={}
    raw=OLD_LOCAL/'final_rule_only_v1/items'
    for name,sha in verification['local_item_hashes'].items():
        path=raw/name
        if p.digest(path)!=sha: raise ValueError('saved item drift: '+name)
        item=json.loads(gzip.decompress(path.read_bytes()))
        row=item['row']
        if row['policy'] not in BASES: continue
        key=(row['seed'],row['family'],row['context'],row['policy'])
        if key in found: raise ValueError('duplicate cached row')
        found[key]=item;hashes[name]=sha
    if len(found)!=1152: raise ValueError('cache denominator')
    return found,hashes


def execute(kind, identity, frozen, initial, tickets, context, policy, metadata=None):
    number=begin(kind,identity);began=time.perf_counter()
    try:
        result,c=(rule.simulate(frozen,initial,tickets,context,policy) if policy in rule.POLICIES else
                  rule.external.simulate(frozen,initial,tickets,context,policy))
        if policy in rule.POLICIES: conformance(result,tickets)
        else: audit.audit(result,tickets)
        row,curves=audit.metrics(result,c,initial,frozen)
        row.update(metadata or {},policy=policy,origin='new_IE_comparison')
        # Separate, independent energy integral over actual state occupancy.
        j=initial['preload_power_w']*120.
        for ss in curves['segments']:
            label='resident_idle' if ss['state']=='idle' else ss['state']
            if label!='resident_idle' and label not in frozen['energy_increment_w']:
                raise ValueError('unsupported energy state')
            dt=max(0.,min(120.,ss['end_s'])-max(0.,ss['start_s']))
            j+=dt*(0. if label=='resident_idle' else frozen['energy_increment_w'][label])
        if abs(j-row['energy_j'])>1e-9: raise ValueError('energy recomputation')
        item=dict(identity=identity,contract_sha256=p.digest(BUNDLE/'contract.json'),
            row=row,result=result,curves=curves,host_wall_s=time.perf_counter()-began)
        path=LOCAL/('items' if kind=='comparison' else 'fixtures')/f'{identity}.json.gz'
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream: stream.write(gzip.compress(json.dumps(item,ensure_ascii=False,allow_nan=False).encode('utf8'),mtime=0))
        journal('completed',number=number,identity=identity,kind=kind,item_sha256=p.digest(path))
        return item
    except BaseException as error:
        journal('failed',number=number,identity=identity,kind=kind,error=repr(error));raise


def run():
    c=prepare();found,oldhashes=cache();inputs=read(ROOT/c['input_path']);frozen,_=p.inputs(p.BUNDLE)
    initial=inputs['initial'];write(LOCAL/'cache_receipt.json',dict(source=c['prior_verification_path'],item_hashes=oldhashes))
    owner=LOCAL/'owner.json'
    with owner.open('x',encoding='utf8') as stream: json.dump(dict(pid=os.getpid(),utc=utc()),stream)
    try:
        if not (LOCAL/'fixtures_complete.json').exists():
            if any(r['event']=='start' and r['kind']=='fixture' for r in entries(LOCAL/'executions.jsonl')):
                raise RuntimeError('partial fixtures; preserve and review instead of repeating starts')
            qs=[dict(id='fixture/'+str(i),ordinal=i,task='classification' if i%2 else 'detection',
                     priority='urgent' if i%2 else 'normal',arrival_ns=int((35.+i*.15)*1e9),
                     deadline_offset_ns=1500000000 if i%2 else 6000000000) for i in range(6)]
            for context in ('mean','long_context'):
                for k,policy in enumerate(rule.POLICIES):
                    execute('fixture',f'{context}_{k}',frozen,initial,qs,context,policy)
            work=inputs['workloads'][0]
            for policy in ('SHARED_EFT','EFT_REFERENCE'):
                item=execute('fixture','preserve_'+policy,frozen,initial,work['tickets'],'mean',policy)
                olditem=found[(work['seed'],work['family'],'mean',policy)]
                if item['result']['ledger']!=olditem['result']['ledger']: raise ValueError('existing baseline ledger changed')
                for key in ('energy_j','peak_ap_c','urgent_p95_ms','normal_mean_ms','deadline_met','completed'):
                    if item['row'][key]!=olditem['row'][key]: raise ValueError('existing baseline metric changed')
            write(LOCAL/'fixtures_complete.json',dict(status='PASS',engine_runs=8,baseline_ledgers_identical=2))
        rows=[];itemhashes={}
        for work in inputs['workloads']:
            for context in ('mean','short_context','long_context'):
                for policy in BASES:
                    item=found[(work['seed'],work['family'],context,policy)]
                    audit.audit(item['result'],work['tickets'])
                    rows.append(dict(item['row'],origin='reused_completed_192'))
                for policy in rule.POLICIES:
                    identity=f"{work['seed']}_{work['family']}_{context}_{policy}"
                    path=LOCAL/'items'/f'{identity}.json.gz'
                    if path.exists():
                        item=json.loads(gzip.decompress(path.read_bytes()))
                        receipt=[r for r in entries(LOCAL/'executions.jsonl') if r['event']=='completed' and r['identity']==identity]
                        if len(receipt)!=1 or receipt[0]['item_sha256']!=p.digest(path) or item['contract_sha256']!=p.digest(BUNDLE/'contract.json'):
                            raise ValueError('resume item binding')
                    else:
                        item=execute('comparison',identity,frozen,initial,work['tickets'],context,policy,
                            dict(seed=work['seed'],family=work['family'],context=context,scope='resource',environment='immediate_allow'))
                    rows.append(item['row']);itemhashes[path.name]=p.digest(path)
                write(LOCAL/'progress.json',dict(new_rows=len(itemhashes),total_new_rows=576,consumption=consumption()))
                if len(itemhashes)%36==0: print(f'{len(itemhashes)}/576',flush=True)
        audit.csv_write(BUNDLE/'results.csv',rows)
        write(BUNDLE/'completion.json',dict(status='completed',utc=utc(),head=head(),dirty=True,
            command='MKL_THREADING_LAYER=SEQUENTIAL; python -B -m tools.d1_ie_dispatch_study run',
            logical_rows=len(rows),new_rows=len(itemhashes),reused_rows=len(found),fixture_runs=8,
            contract_sha256=p.digest(BUNDLE/'contract.json'),consumption=consumption(),
            results_sha256=p.digest(BUNDLE/'results.csv'),new_item_hashes=itemhashes,
            saved_cache_receipt_sha256=p.digest(LOCAL/'cache_receipt.json'),
            experiment_ready=False,strict_supported=False))
        return dict(status='completed',consumption=consumption(),logical_rows=len(rows))
    finally:
        if owner.exists() and read(owner)['pid']==os.getpid(): owner.unlink()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','run','status'))
    a=parser.parse_args().action
    print(json.dumps(run() if a=='run' else prepare() if a=='prepare' else consumption(),ensure_ascii=False,indent=2))
