"""Frozen final comparisons; reused v2 controls and explicit actual-execution counts."""
from __future__ import annotations
import argparse
import copy
import gzip
import json
import os
from pathlib import Path
import signal
import time
import traceback
import uuid
from tools import d1_rl_amount_campaign as amount
from tools import d1_rule_recombination as rules
from tools import d1_queue_ppo_learning_amount as analysis
from tools import d1_rules_rl_common as common

v=amount.v


def write_gzip(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.tmp')
    with temp.open('wb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as zipped:
            zipped.write(json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf8'))
        raw.flush();os.fsync(raw.fileno())
    os.replace(temp,path)


def read_gzip(path):
    with gzip.open(path,'rt',encoding='utf8') as f:return json.load(f)


def freeze(folder):
    folder=Path(folder);root=folder/'rl';cfg=common.read(folder/'rl_contract_before_run.json')['configuration']
    state=common.read(root/'state.json')
    policies=[]
    for milestone in state['milestones']:
        for kind in ('latest','best'):
            path=root/milestone[kind+'_actor'];obj=common.read(path)
            policies.append(dict(policy=f'{milestone["identity"]}_ep{milestone["episodes"]}_{kind}',
                variant=milestone['variant'],seed=milestone['seed'],episodes=milestone['episodes'],kind=kind,
                best_update=milestone['best_update'],last_update=milestone['update'],
                validation_key=milestone['best_key'] if kind=='best' else milestone['latest_key'],
                validation_eligible=(milestone['best_key'] if kind=='best' else milestone['latest_key'])[0]==0 and
                    (milestone['best_key'] if kind=='best' else milestone['latest_key'])[1]==0 and
                    (milestone['best_key'] if kind=='best' else milestone['latest_key'])[3]==0,
                file=str(path.relative_to(folder)),file_sha256=common.digest(path),model_sha256=obj['sha256']))
    if not policies:raise ValueError('no preserved learner milestone for evaluation')
    common_points=[n for n in sorted({p['episodes'] for p in policies})
        if len({(p['variant'],p['seed']) for p in policies if p['episodes']==n})==6]
    spec=dict(version='rules-rl-frozen-final-v1',policies=policies,
        baselines=cfg['source_design']['baselines'],recombination=[rules.PREFIX,rules.COMPLETE],
        test=cfg['test'],common_complete_episode_points=common_points,
        training_status=state['status'],training_errors=state.get('errors',[]),
        sources_sha256={str(p.relative_to(common.ROOT)).replace('\\','/'):common.digest(p)
            for p in (Path(__file__),Path(rules.__file__),Path(amount.__file__))},
        prior_table_sha256=common.digest(common.ROOT/'output/queue_ppo_v2_evaluation_v1/test.csv'),
        old_v2_controls_reused=True,final_test_already_seen=True,new_independent_holdout=False,
        physical_model_sha256=v.q.p.MODEL_SHA,initial_sha256=v.q.p.INITIAL_SHA,
        frozen_utc=common.utc(),device_commands=0,experiment_ready=False)
    path=folder/'final_comparison_freeze.json'
    if path.exists():
        old=common.read(path)
        if any(old[k]!=spec[k] for k in spec if k!='frozen_utc'):raise ValueError('final comparison changed after freeze')
        return old
    common.atomic(path,spec);return spec


def run(folder=common.OUTPUT,resume=False):
    folder=Path(folder);out=folder/'evaluation';lock=folder/'evaluation_owner.json';run_id=uuid.uuid4().hex
    if (folder/'rl_owner.json').exists() or v.q.LOCK.exists() or lock.exists():raise ValueError('active/unresolved execution; no duplicate evaluator')
    spec=common.read(folder/'final_comparison_freeze.json') if resume else freeze(folder)
    for name,sha in spec['sources_sha256'].items():
        if common.digest(common.ROOT/name)!=sha:raise ValueError('frozen comparison source drift')
    baseline_path=common.ROOT/'output/queue_ppo_v2_evaluation_v1/test.csv'
    if common.digest(baseline_path)!=spec['prior_table_sha256']:raise ValueError('prior table changed')
    old=analysis.typed_csv(baseline_path)
    baselines={(r['trace_seed'],r['family'],r['context'],r['policy']):r for r in old if r['policy'] in spec['baselines']}
    if len(baselines)!=len(spec['test'])*len(spec['baselines']):raise ValueError('complete baseline denominator required')
    frozen,case=v.q.p.inputs(v.q.p.BUNDLE);initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
    if resume:
        state=common.read(out/'state.json')
        if state['status'] not in ('paused','failed_io'):raise ValueError('not an eligible evaluator resume')
    else:
        out.mkdir(exist_ok=False);state=dict(cursor=0,status='running',actual_rl=0,actual_recombination=0,reused=0,errors=[])
    state['status']='running';budget=common.Budget(folder);pause=False
    previous=signal.getsignal(signal.SIGINT)
    def request_pause(*_):
        nonlocal pause
        pause=True
    signal.signal(signal.SIGINT,request_pause)
    policies=[dict(policy=p,variant=p,kind='baseline') for p in spec['baselines']]+[
        dict(policy=p,kind='recombination') for p in spec['recombination']]+spec['policies']
    jobs=[(case,policy) for case in spec['test'] for policy in policies]
    cache={}
    for path in (out/'cache').glob('*.json.gz'):
        item=read_gzip(path);cache[item['cache_key']]=path
    networks={}
    with lock.open('x',encoding='utf8') as f:json.dump(dict(pid=os.getpid(),run_id=run_id,started_utc=common.utc()),f)
    try:
        while state['cursor']<len(jobs):
            budget.check(reserve=300)
            tickets_case,policy=jobs[state['cursor']];seed,family,context=tickets_case
            item_path=out/'items'/f'{state["cursor"]:06d}.json.gz'
            if item_path.exists():
                item=read_gzip(item_path)
                if item['case']!=tickets_case or item['policy']!=policy['policy']:raise ValueError('orphan result identity mismatch')
                state['reused']+=1
            else:
                key=f'{seed}/{family}/{context}/{policy.get("model_sha256",policy["policy"])}'
                ledger=None;decisions=None;reuse_source=None
                if policy['kind']=='baseline':
                    row=copy.deepcopy(baselines[seed,family,context,policy['policy']]);reuse_source='original_v2_test.csv'
                elif key in cache:
                    previous_item=read_gzip(cache[key]);row=copy.deepcopy(previous_item['row']);reuse_source=str(cache[key].relative_to(folder))
                elif policy['kind']=='recombination':
                    runtime_fixture=folder/f'full_runtime_{policy["policy"]}.json'
                    prior=common.read(runtime_fixture) if runtime_fixture.exists() else None
                    if prior and prior.get('case')==tickets_case and prior.get('source_sha256')==common.digest(rules.__file__):
                        row=prior['row'];reuse_source=str(runtime_fixture.relative_to(folder))
                    else:
                        row,result,controller,_=budget.execute('recombination','final_test',lambda:rules.simulate(
                            frozen,initial,v.q.old.workload(family,seed),context,policy['policy']),
                            case=tickets_case,policy=policy['policy'])
                        ledger=result['ledger'];decisions=result['decisions'];state['actual_recombination']+=1
                else:
                    if common.digest(folder/policy['file'])!=policy['file_sha256']:raise ValueError('frozen actor file drift')
                    if policy['model_sha256'] not in networks:networks[policy['model_sha256']]=v.q.load_actor(folder/policy['file'])
                    network=networks[policy['model_sha256']]
                    row,result,_,_=budget.execute('rl','final_test',lambda:v.simulate(frozen,initial,
                        v.q.old.workload(family,seed),context,policy['variant'],network,True),
                        case=tickets_case,policy=policy['policy'],model_sha256=policy['model_sha256'])
                    ledger=result['ledger'];decisions=result['decisions'];state['actual_rl']+=1
                row=dict(row,trace_seed=seed,family=family,context=context,policy=policy['policy'],
                    kind=policy['kind'],variant=policy.get('variant'),learning_seed=policy.get('seed'),
                    episodes=policy.get('episodes'),best_update=policy.get('best_update'),
                    validation_eligible=policy.get('validation_eligible'),reuse_source=reuse_source)
                item=dict(case=tickets_case,policy=policy['policy'],row=row,ledger=ledger,decisions=decisions,cache_key=key)
                write_gzip(item_path,item)
                if policy['kind']!='baseline' and key not in cache:
                    cache_path=out/'cache'/f'{v.design.digest_value(key)}.json.gz';write_gzip(cache_path,item);cache[key]=cache_path
                if reuse_source is not None:state['reused']+=1
            state['cursor']+=1
            common.atomic(out/'state.json',state)
            if state['cursor']%len(policies)==0:
                obj=dict(stage='final_comparison',completed_cases=state['cursor']//len(policies),total_cases=len(spec['test']),
                    state=state,utc=common.utc())
                common.atomic(out/'progress.json',obj);budget.publish(stage='final_comparison')
                print(json.dumps(obj,ensure_ascii=False),flush=True)
            if pause:state['status']='paused';break
        if state['cursor']==len(jobs):state['status']='completed'
    except common.BudgetStop as e:state.update(status='budget_stopped',stop_reason=str(e))
    except BaseException as e:
        error=dict(type=type(e).__name__,message=str(e),stack=traceback.format_exc(),utc=common.utc());state['errors'].append(error)
        state['status']='failed_io' if isinstance(e,OSError) else 'failed_numeric_or_contract'
        common.atomic(out/f'error_{len(state["errors"])}.json',error);raise
    finally:
        common.atomic(out/'state.json',state);budget.publish(stage='evaluation_'+state['status'])
        signal.signal(signal.SIGINT,previous)
        if lock.exists() and common.read(lock).get('run_id')==run_id:lock.unlink()
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');args=p.parse_args()
    print(json.dumps(run(resume=args.resume),ensure_ascii=False),flush=True)
