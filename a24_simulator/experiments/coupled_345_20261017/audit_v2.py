"""Saved-only independent power/RC conservation and neural/optimizer replay."""
from pathlib import Path
import gzip
import hashlib
import io
import json
import math
import sys
import copy
import numpy as np
import torch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G
from nn_train import Learner,digest
from dynamics import Config,Physics
from controller import Controller
G.OWN_TOKENS+=('coupled_345_20261017','shared_cost_policy_20261017','shared_activation_20261017')


def read(path):
    b=path.read_bytes();return json.loads(gzip.decompress(b) if path.suffix=='.gz' else b)


def pt(path):return torch.load(io.BytesIO(gzip.decompress(path.read_bytes())),map_location='cpu',weights_only=False)


def main():
    op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir']
    G.require((out/'COMPLETE.json').exists() and not (out/'AUDIT.json').exists(),'Completed unaudited operation required')
    guard=G.process_guard(Path(__file__).resolve());G.free_guard([ROOT,'D:/'])
    checks=0;maximum=0.;numeric=0
    def need(v,reason):
        nonlocal checks
        checks+=1;G.require(v,reason)
    def close(a,b,reason,tol=1e-7):
        nonlocal maximum,numeric
        maximum=max(maximum,abs(a-b));numeric+=1;need(abs(a-b)<=tol,reason+': '+str((a,b)))
    for p in [*op['sources'],*op['input_pins']]:need(G.sha(p['path'])==p['sha256'] and Path(p['path']).stat().st_size==p['bytes'],'Source bytes')
    post=read(HERE/'AUDIT_OPERATION_V2.json')
    for p in post['pins']:need(G.sha(p['path'])==p['sha256'] and Path(p['path']).stat().st_size==p['bytes'],'Strengthened auditor bytes')
    result=read(out/'RESULT.json');terminal=read(out/'COMPLETE.json');selection=read(out/'SELECTION_FROZEN.json')
    need(G.sha(out/'RESULT.json')==terminal['result_sha256'],'Terminal bytes')
    receipts=[json.loads(s) for s in (out/'receipts.jsonl').read_text().splitlines() if s]
    starts=[r for r in receipts if r['event']=='START'];ends=[r for r in receipts if r['event']=='COMPLETE']
    need(len(starts)==len(ends)==op['planned_START']==602,'602 completed unique starts')
    need(len({r['identity'] for r in starts})==602 and not any(r['event']=='FAIL' for r in receipts),'No duplicates/hidden failures')
    need(len(result['rows'])==598,'Four P0 runs separately accounted')
    need(selection['fresh_outcomes_opened']==0,'DEV-only selection')
    first_fresh=next(i for i,r in enumerate(starts) if r['kind']=='FRESH')
    need(all(r['kind'] not in ('TRAIN','DEV','P0') for r in starts[first_fresh:]),'Training/selection precede fresh outcomes')
    for r in starts[first_fresh:]:need(r['selection_sha256']==G.sha(out/'SELECTION_FROZEN.json'),'Frozen selection bound to evaluations')
    raw_cache={};nn_actions=0;chosen_forecast_replays=0
    model=read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')
    solo=dict(zip(model['supported_states'],model['coefficients_W_proxy']));pair=solo.pop('classification_GPU+detection_CPU');solo['detection_GPU']=.6013808404579677
    H=solo['classification_GPU']+solo['detection_CPU']-pair
    cases=read(Path(op['inputs']['path']));by_case={c['id']:c for group in ('train','dev','fresh') for c in cases[group]}
    model_cache={}
    for row in result['rows']:
        name=row['label'];receipt=next(r for r in ends if r['label']==name);raw_path=out/(name+'.raw.json.gz')
        need(G.sha(raw_path)==row['raw_sha256']==receipt['raw_sha256'],'Raw SHA')
        need(G.sha(out/(name+'.json'))==receipt['result_sha256'],'Summary SHA')
        raw=read(raw_path);r=raw['result'];c=r['config'];q=r['requests'];case=by_case[row['case']]
        for key,value in op['physics'].items():
            expected=row['strength'] if key=='strength' else row['tick_s'] if key=='tick_s' else value
            close(c[key],expected,'Frozen physics/scenario configuration')
        inc=area=0.;workarea=0.;rates={x['request_id']:[0.]*5 for x in q if x['dispatch_ns'] is not None};peak=0
        # Independent instantaneous power and the integrated RC energy balance.
        for t in r['trace']:
            a,b=t['start_ns']/1e9,t['end_ns']/1e9;dt=b-a;T=t['state']['temperature_c'];z=t['state']['shared_z']
            need(len(t['active'])<=2 and len({x['route'] for x in t['active']})==len(t['active']),'One CPU one GPU')
            dyn=0.
            leak=math.exp(min(math.log(3.),max(-math.log(3.),c['strength']*c['leakage_per_c']*(T-c['reference_c']))))
            midpoint=(t['start_ns']+t['end_ns'])/2
            active_actual=[x for x in q if x['dispatch_ns'] is not None and x['dispatch_ns']<=midpoint and (x['available_ns'] is None or x['available_ns']>midpoint)]
            need(len(active_actual)==len(t['active']),'Trace occupancy reconstructed from completed schedule')
            for active in t['active']:
                true=next(x for x in active_actual if x['route']==active['route'])
                boundaries=[true.get(k) for k in ('execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','available_ns')]
                stage=sum(x is not None and x<=midpoint for x in boundaries)
                need(stage==active['stage'] and true['task']==active['task'],'Current phase from recorded boundaries')
                slope=c['cpu_slope'] if active['route']=='CPU' else c['gpu_slope']
                f=max(c['minimum_speed'],1/(1+c['strength']*slope*max(0,T-c['onset_c']))) if stage==1 else 1.
                close(f,t['speeds'][active['route']],'Public current thermal speed')
                rates[true['request_id']][stage]+=dt*f
                cell=('classification' if active['task']=='C' else 'detection')+'_'+active['route']
                dyn+=(solo[cell]-H)*((1-c['leakage_fraction'])*f**3+c['leakage_fraction']*leak)
            shared=H*dt if t['active'] else H*z*c['idle_tail_s']*(-math.expm1(-dt/c['idle_tail_s']))
            expected=dyn*dt+shared
            close(expected,t['increment'],'Independent state power')
            close(t['next_state']['temperature_c']-T,(c['thermal_resistance']*expected-(t['temperature_area']-c['idle_c']*dt))/c['thermal_tau_s'],'Integrated RC conservation')
            if a>=35-1e-9 and b<=case['drain_stop_s']+1e-9:
                inc+=expected;area+=t['temperature_area'];peak=max(peak,t['peak'])
            if a>=35-1e-9 and b<=case['service_stop_s']+1e-9:workarea+=t['temperature_area']
        for x in q:
            if x['available_ns'] is not None:
                for actual,work in zip(rates[x['request_id']],x['timing']['stages_ns']):close(actual,work/1e9,'Immutable latent work conservation',2e-8)
            if x['response_ns'] is not None:need(x['response_ns']==x['output_ready_ns' if x['task']=='C' else 'persist_complete_ns'],'Task-specific response boundary')
        close(inc,row['metrics']['increment_J_proxy'],'Energy from independent state powers')
        close(workarea/(case['service_stop_s']-35),row['metrics']['mean_AP_c'],'Common work-window AP')
        close(peak,row['metrics']['peak_AP_c'],'Peak temperature')
        on=sum(x['response_ns'] is not None and x['response_ns']<=x['deadline_ns'] and x['response_ns']/1e9<=case['drain_stop_s'] for x in q)
        need(on==row['metrics']['on_time'],'All planned outcomes retained')
        decisions=r['decisions'];need(len(decisions)==len(raw['calls']),'Every actual action recorded')
        nonforced=[]
        for d,call in zip(decisions,raw['calls']):
            need(d['time_ns']==call['time_ns'] and d['action']==call['action'],'Sequential same-clock action applied')
            if call['common_coalescing']:continue
            nonforced.append(call);i=call['chosen']
            need(call['mask'][i] and call['actions'][i]==call['action'],'Physical legal chosen action')
            if call['forecasts'][i] is not None:
                close(call['x'][i][15],(call['sensor']['temperature_c']-26)/10,'Actual heat input',1e-5)
                close(call['x'][i][16],call['sensor']['shared_z'],'Actual cost memory input',1e-5)
                need(call['fixed_ATC_prior_logit']==0 and not call['future_actual_work_used'] and not call['future_arrivals_used'],'No fixed prior or declared future truth')
                for f,x in zip(call['forecasts'],call['x']):
                    for k in range(5):close(x[23+k],max(-10,min(10,f['costs'][k])),'Forecast objective input',1e-5)
                if row['kind']=='FRESH' and len(nonforced)%16==1:
                    p=Physics(model,Config(**c));actor=Controller(None,p,case,'EXACT')
                    vectors={tuple(key.split('|')):v for key,v in call['nominal_vectors'].items()}
                    pred=actor.preview(d['public_state'],call['nominal_ready'],call['nominal_owners'],vectors,call['action'])
                    close(pred['energy'],call['forecasts'][i]['energy'],'Saved public nominal replay')
                    chosen_forecast_replays+=1
        if row['policy']=='RL':
            frames=pt(out/(name+'.frames.pt.gz'))
            close(float(np.max(abs(frames['costs'].sum(0)-np.array(row['metrics']['cost_vector'])))),0,'Reward/final objective equality',1e-6)
            need(len(frames['frames'])==len(nonforced),'One NN frame per neural decision')
            for call,frame in zip(nonforced,frames['frames']):
                need(np.array_equal(frame['x'],np.asarray(call['x'],dtype=np.float32)) and np.array_equal(frame['mask'],np.asarray(call['mask'],dtype=bool)),'Exact applied typed input/action binding')
            if row['kind']=='FRESH':
                cp=next(cp for cp in selection['by_seed'] if cp['seed']==int(name.split('_S')[-1]))
                key=cp['path']
                if key not in model_cache:
                    learner=Learner(cp['seed']);learner.restore(pt(out/key));model_cache[key]=learner
                learner=model_cache[key]
                for call,frame in zip(nonforced,frames['frames']):
                    i,replay=learner.choose(frame,False);need(i==frame['index']==call['chosen'],'Exact NN greedy replay')
                    close(replay['old_logp'],frame['old_logp'],'Exact neural logprob',1e-5);nn_actions+=1
        if row['kind']=='FRESH':raw_cache[name]=raw
    # Replay the first actual two-episode PPO update independently for each seed,
    # including sampled actions, Adam and both random generator states.
    for seed in op['learner_seeds']:
        learner=Learner(seed);learner.restore(pt(out/('SEED_%d_EP000.pt.gz'%seed)))
        for episode in (1,2):
            saved=pt(out/('TRAIN_S%d_EP%03d.frames.pt.gz'%(seed,episode)))
            for f in saved['frames']:
                chosen,replay=learner.choose(f,True);need(chosen==f['index'],'Training action RNG replay');close(replay['old_logp'],f['old_logp'],'Training policy replay',1e-5)
            learner.add(saved['frames'],saved['costs'])
        target=pt(out/('SEED_%d_EP002.pt.gz'%seed));need(digest(learner.net)==target['network_sha256'],'Actual first Adam update replay')
        actual=learner.optimizer.state_dict();expected=target['optimizer']
        need(actual['param_groups']==expected['param_groups'] and set(actual['state'])==set(expected['state']),'Adam state schema/groups')
        for param,state in expected['state'].items():
            for key,value in state.items():
                if torch.is_tensor(value):need(torch.equal(actual['state'][param][key],value),'Exact Adam moment/step tensor')
                else:need(actual['state'][param][key]==value,'Exact Adam scalar')
        need(torch.equal(learner.action_rng.get_state(),target['action_rng']) and torch.equal(learner.shuffle_rng.get_state(),target['shuffle_rng']),'Action/shuffle RNG exact')
        final=pt(out/('SEED_%d_EP128.pt.gz'%seed));need(final['updates']==64 and final['network_sha256']!=pt(out/('SEED_%d_EP000.pt.gz'%seed))['network_sha256'],'64 genuine updates per seed')
    G.write_new(out/'AUDIT.json',dict(status='PASS_INDEPENDENT_POWER_RC_WORK_AND_NEURAL_REPLAY',checks=checks,numeric_checks=numeric,
        max_absolute_difference=maximum,NN_actions_replayed=nn_actions,nominal_candidates_replayed=chosen_forecast_replays,
        first_PPO_Adam_updates_replayed=3,environment_restarts=0,new_environment_START=0,
        source_operation_sha256=G.sha(HERE/'OPERATION.json'),result_sha256=G.sha(out/'RESULT.json'),guard=guard,measured_J=None,physical_accuracy_verified=False))
    print(json.dumps(dict(status='PASS',checks=checks,NN_actions=nn_actions,max_difference=maximum)))


if __name__=='__main__':main()
