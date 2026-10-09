"""Registered <=32 native implementation checks. Never trains or uses a device."""
from __future__ import annotations

import argparse
import copy
import csv
import gzip
import hashlib
import json
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from tools import d1_list_candidate_rl as x
from tools import d1_list_candidate_rl_engine as engine
from tools import d1_arrival_explore as legacy
from tools import d1_external_rules as external
from tools import d1_ie_dispatch as ie
from tools import d1_triton_rules as triton
from tools import d1_ie_candidates_v2 as previous

ROOT=x.ROOT


def serial(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,torch.Tensor):return value.detach().cpu().tolist()
    if isinstance(value,dict):return {str(k):serial(v) for k,v in value.items()}
    if isinstance(value,(tuple,list,set)):return [serial(v) for v in value]
    return value


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(serial(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_unconsumed_phase(output, evidence_name):
    """Reject retries before overwriting registered/completed evidence."""
    if (Path(output) / evidence_name).exists():
        raise FileExistsError('phase evidence already exists; preserve it and do not reuse consumed IDs')


def ticket(rid,task,arrival,ordinal):
    return dict(id=rid,task=task,priority='urgent' if task=='classification' else 'normal',ordinal=ordinal,
                arrival_ns=round(arrival*1e9),deadline_offset_ns=1500000000 if task=='classification' else 6000000000)


def c2_tickets(frozen,arm):
    profile=x.p.profile(frozen)
    d=sum(profile['detection_CPU_normal'])/1e9;g=sum(profile['classification_GPU_urgent'])/1e9
    now=41.;qs=[]
    for i in range(9):qs.append(ticket('OD'+str(i+1),'detection',now-9*d,len(qs)))
    for i in range(4):qs.append(ticket('OG'+str(i+1),'classification',now-d-2*g,len(qs)))
    qs.append(ticket('C1','classification',now-1.1,len(qs)))
    qs.append(ticket('D1','detection',now-5.15,len(qs)))
    qs.append(ticket('C2','classification',now-(1. if arm=='A' else .5),len(qs)))
    counts={'classification':2,'detection':1}
    for i,task in enumerate(('detection','classification','detection','classification','detection','classification','detection','classification','detection')):
        counts[task]+=1;qs.append(ticket(('C' if task=='classification' else 'D')+str(counts[task]),task,now-.3+.025*i,len(qs)))
    return qs


class C2Script:
    def __init__(self,first):self.first=first;self.cut=None;self.cut_actions=None
    def __call__(self,c,encoded,actions,queue):
        kinds={a['kind']:i for i,a in enumerate(actions)}
        if self.cut is not None:
            saved=c.selector;c.selector=None
            try:return c.choose(encoded,actions,queue)
            finally:c.selector=saved
        finished={rid for rid,stage in c.phase_cursors.items() if stage==4}
        if all('OD'+str(i+1) in finished for i in range(9)) and all('OG'+str(i+1) in finished for i in range(4)):
            self.cut=copy.deepcopy(encoded);self.cut_actions=copy.deepcopy(actions)
            return kinds[self.first]
        heads=x.heads_of(queue);cq=heads['classification'];dq=heads['detection']
        if cq and cq['id']=='OG3' and dq and dq['id']=='OD9':
            if 'PAIR_NOW' in kinds:return kinds['PAIR_NOW']
            if 'DEFER_ALL_SHORT' in kinds:return kinds['DEFER_ALL_SHORT']
        if cq and cq['id'].startswith('OG') and 'C_GPU_NOW' in kinds:return kinds['C_GPU_NOW']
        if dq and dq['id'].startswith('OD') and 'D_CPU_NOW' in kinds:return kinds['D_CPU_NOW']
        if 'DEFER_ALL_SHORT' in kinds:return kinds['DEFER_ALL_SHORT']
        raise ValueError('registered prefix has no legal bank choice')


class Budget:
    def __init__(self,output):
        self.output=output;self.path=output/'execution.jsonl';self.started=time.monotonic();self.rows=[]
        if self.path.exists():
            for line in self.path.read_text(encoding='utf8').splitlines():
                value=json.loads(line)
                if 'event' not in value:self.rows.append(value)
                elif value['event'] in ('completion','failure'):self.rows[value['number']-1].update(value)
        registration=output/'registration.json'
        self.wall_deadline=(datetime.fromisoformat(json.loads(registration.read_text(encoding='utf8'))['recorded_utc']).timestamp()+6900
                            if registration.exists() else time.time()+6900)
    def append(self,value):
        with self.path.open('a',encoding='utf8') as f:
            f.write(json.dumps(serial(value),ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def call(self,identity,module,c,requests,frozen,initial,context='mean',zero=False):
        if len(self.rows)>=32 or time.time()>=self.wall_deadline:raise TimeoutError('32-native/2h-save-reserve gate')
        if any(row['identity']==identity for row in self.rows):raise ValueError('consumed identity')
        row=dict(number=len(self.rows)+1,identity=identity,status='started',planned=len(requests),learning_starts=0)
        self.rows.append(row);self.append(row)
        self.output.joinpath('source_versions').mkdir(exist_ok=True)
        for p in (Path(x.__file__),Path(engine.__file__),Path(__file__)):
            archived=self.output/'source_versions'/(p.stem+'_'+sha(p)+'.py')
            if not archived.exists():archived.write_bytes(p.read_bytes())
        actual=x.p.profile(frozen,context)
        vectors=dict(cells={key:[dict(source_request_id='common_measured_context_'+context,durations_ns=[0.]*5 if zero else values) for _ in range(4)] for key,values in actual.items()})
        try:
            began=time.perf_counter()
            result=module.simulate(dict(protocol=x.p.VERSION,cells=x.p.profile(frozen)),vectors,requests,
                policy=c.policy,settings=external.settings(),seed=201,decision_provider=c)
            duration=time.perf_counter()-began
            _,costs,end=x.p.account(result,initial,frozen)
            full=result['metrics']['completion']==1
            metrics=dict(planned=len(requests),completed=sum(r['status']=='succeeded' for r in result['ledger']),
                incomplete=sum(r['status']!='succeeded' for r in result['ledger']),
                urgent_failure=sum(r['priority']=='urgent' and ('response_ns' not in r or r['late_success']) for r in result['ledger']),
                normal_failure=sum(r['priority']=='normal' and ('response_ns' not in r or r['late_success']) for r in result['ledger']),
                urgent_p95_ms=result['metrics']['urgent_p95_ms'],normal_mean_ms=result['metrics']['normal_mean_ms'],
                energy_j=costs['whole_120s_j'] if full else None,peak_ap_c=max(costs['ap_path']) if full else None,
                native_seconds=duration)
            item=dict(result=result,row=metrics,curve=list(zip(range(35,end+1),costs['ap_path'])))
            if isinstance(c,x.Controller):item.update(events=c.events,controls=c.controls,snapshots=c.snapshots)
            path=self.output/'items'/(identity+'.json.gz');path.parent.mkdir(exist_ok=True)
            path.write_bytes(gzip.compress(json.dumps(serial(item),ensure_ascii=False,allow_nan=False).encode()))
            row.update(status='completed',completed=metrics['completed'],artifact_sha256=sha(path),seconds=duration)
            self.append(dict(event='completion',**row));return item
        except BaseException as error:
            row.update(status='failed',completed=None,error=repr(error))
            self.append(dict(event='failure',**row))
            write(self.output/'failures'/(identity+'.json'),dict(row=row,traceback=traceback.format_exc(),
                public_events=getattr(c,'events',[]),controls=getattr(c,'controls',[])))
            raise


def abi(encoded):
    return dict(tensors={key:dict(shape=list(encoded[key].shape),dtype=str(encoded[key].dtype),sha256=hashlib.sha256(encoded[key].tobytes()).hexdigest())
                         for key in ('state','candidates','mask')},base=encoded['base'],kinds=encoded['kinds'],
                credit=encoded['credit'],now_ns=encoded['now_ns'],pending=encoded['pending'],hold=encoded['hold'],event_seq=encoded['event_seq'])


def additional_checks(output):
    assert_unconsumed_phase(output, 'observation_repair_before_run.json')
    output=Path(output);budget=Budget(output)
    if (output/'owner.lock').exists():raise ValueError('gate still owned')
    lock=output/'owner.lock';lock.write_text(str(os.getpid()),encoding='ascii')
    frozen,case=x.p.inputs(x.p.BUNDLE);initial=case['initial']
    original=json.loads((output/'summary.json').read_text(encoding='utf8'))
    if not original['C2_feature_repair_needed']:raise ValueError('no registered alias evidence for feature repair')
    record=dict(status='running',repair_variant='head2+C_next',repair_reason='actual input alias plus registered A service-loss difference, not opposite optimal first actions',
                prior_native_starts=len(budget.rows),new_native_cap=32,registration=json.loads((output/'registration.json').read_text(encoding='utf8')),
                source_sha256=sha(Path(x.__file__)),recorded_utc=datetime.now(timezone.utc).isoformat(),repair=[],gradient=None,checkpoint=None)
    write(output/'observation_repair_before_run.json',record)
    try:
        cuts={}
        for arm in ('A','B'):
            for first in ('C_CPU_NOW','PAIR_NOW'):
                identity='repair_'+arm+'_'+first;script=C2Script(first)
                c=x.Controller(frozen,initial,selector=script,feature_variant='head2+C_next')
                item=budget.call(identity,engine,c,c2_tickets(frozen,arm),frozen,initial)
                old=json.loads(gzip.decompress((output/'items'/('c2_'+arm+'_'+first+'.json.gz')).read_bytes()))
                for key in ('ledger','transitions','metrics','decisions'):
                    if old['result'][key]!=item['result'][key]:raise ValueError('repair changed fixed-control execution '+key)
                cuts[identity]=copy.deepcopy(script.cut)
                record['repair'].append(dict(identity=identity,original_execution_exact=True,cut=abi(script.cut),
                    schema_id=c.schema_id,new_field_value=float(script.cut['state'][1]),row=item['row']))
        for first in ('C_CPU_NOW','PAIR_NOW'):
            a,b=cuts['repair_A_'+first],cuts['repair_B_'+first]
            changed=np.flatnonzero(a['state']!=b['state']).tolist()
            if changed != [1] or a['candidates'].tobytes()!=b['candidates'].tobytes() or a['mask'].tobytes()!=b['mask'].tobytes():
                raise ValueError('repair did not isolate public C-next field')
        torch.manual_seed(97);network=x.ActorCritic();controller=x.Controller(frozen,initial,x.PPO,network=network,
            deterministic=False,feature_variant='head2+C_next')
        requests=external.old.workload('burst',812010001)
        item=budget.call('sampled_forward_diagnostic',engine,controller,requests,frozen,initial)
        reference=json.loads(gzip.decompress((output/'items'/('variant_'+x.L0+'.json.gz')).read_bytes()))['row']
        data,rewards,costs,valid=x.episode_targets(controller,item['row'],item['curve'],reference)
        before={key:value.clone() for key,value in network.state_dict().items()}
        parts=x.ppo_losses(network,[data],[0.,10.,1.,1.,1.])
        if torch.count_nonzero(parts['direct_energy_advantage']).item()!=0:raise ValueError('lambda-zero direct energy term')
        targets=torch.from_numpy(np.stack([d['target'] for d in data]))
        network.zero_grad(set_to_none=True)
        j_value=(parts['values'][:,1]-targets[:,1]).square().mean();j_value.backward(retain_graph=True)
        shared_gradient=math_norm(network.state.parameters())
        network.zero_grad(set_to_none=True);parts['loss'].backward()
        gradient=dict(sampled_choices=parts['sampled_choices'],direct_energy_term_max=float(parts['direct_energy_advantage'].abs().max()),
            shared_encoder_J_critic_gradient=shared_gradient,actor_gradient=math_norm(network.actor.parameters()),
            critic_gradient=math_norm(network.critic.parameters()),reward_sum=float(rewards.sum()),
            expected_reward=reference['peak_ap_c']-item['row']['peak_ap_c'],costs=costs,valid=valid,
            optimizer_steps=0,learning_episodes=0)
        if any(not torch.equal(before[k],v) for k,v in network.state_dict().items()):raise ValueError('diagnostic changed weights')
        record['gradient']=gradient
        optimizer=torch.optim.Adam(network.parameters(),lr=.0003,eps=1e-5)
        archive=output/'controller_rng_checkpoint.pt'
        x.save_checkpoint(archive,controller,network,optimizer,[1.,10.,1.,1.,1.],data[:1],dict(native_starts=len(budget.rows),learning_starts=0))
        expected=(__import__('random').random(),np.random.random(),torch.rand(4))
        clone_net=x.ActorCritic();clone=x.Controller(frozen,initial,x.PPO,network=clone_net,feature_variant='head2+C_next')
        clone_optimizer=torch.optim.Adam(clone_net.parameters(),lr=.0003,eps=1e-5)
        payload=x.load_checkpoint(archive,clone,clone_net,clone_optimizer)
        actual=(__import__('random').random(),np.random.random(),torch.rand(4))
        if expected[:2]!=actual[:2] or not torch.equal(expected[2],actual[2]):raise ValueError('archive RNG mismatch')
        if any(not torch.equal(v,clone_net.state_dict()[k]) for k,v in network.state_dict().items()):raise ValueError('archive weights mismatch')
        wrong=x.Controller(frozen,initial,x.PPO,network=clone_net)
        try:x.load_checkpoint(archive,wrong,clone_net,clone_optimizer)
        except ValueError:pass
        else:raise ValueError('old schema accepted new feature archive')
        record['checkpoint']=dict(controller_state_rng_weights_preserved=True,Adam_state_saved=True,Adam_state_nonempty=bool(payload['optimizer']['state']),
            cross_schema_rejected=True,live_engine_or_additional_learning_identity_tested=False)
        record['status']='completed'
    except BaseException as error:
        record.update(status='stopped_error',error=repr(error),traceback=traceback.format_exc())
    finally:
        record['consumption']=dict(new_native_environment_starts=len(budget.rows),additional_native_starts=len(budget.rows)-24,
            cumulative_environment_starts=6517+len(budget.rows),new_learning_starts=0,cumulative_learning_starts=641,device_commands=0,
            failed=sum(row['status']=='failed' for row in budget.rows))
        write(output/'additional_checks.json',record)
        if lock.read_text(encoding='ascii')==str(os.getpid()):lock.unlink()
    print(json.dumps(serial({k:record[k] for k in ('status','consumption','gradient','checkpoint') if k in record}),ensure_ascii=False,indent=2))
    return record


def math_norm(parameters):
    return float(sum(p.grad.detach().square().sum().item() for p in parameters if p.grad is not None)**.5)


class RepresentationTap:
    """Observe old actions without changing them. Pointwise upper-credit only."""
    protocol=x.p.VERSION
    def __init__(self,inner,frozen,initial):
        self.inner=inner;self.policy=inner.policy
        self.observer=x.Controller(frozen,initial,feature_variant='head2+C_next')
        self.records=[]
    def on_public_event(self,event):self.observer.on_public_event(event)
    def observe(self,now,lanes):
        self.inner.observe(now,lanes);self.observer.observe(now,lanes)
    def __call__(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        actions=self.observer.bank(queue,lanes,now)
        out=self.inner(config,queue,lanes,now,settings,thermal_model,current_ap)
        selected=out.get('selected');kind=out.get('action_kind');until=out.get('wait_until_ns')
        heads=x.heads_of(queue);head_ids={q['id'] for q in heads.values() if q}
        status='unclassified';reason=None
        if selected:
            if selected['request_id'] not in head_ids:status='excluded';reason='head_restriction'
            elif not x.legal(selected,queue,lanes):status='excluded';reason='ownership_or_support'
            elif any(a['jobs']==[selected] for a in actions):status='included_immediate'
            elif any(selected in a['jobs'] for a in actions):status='included_bundle_primitive';reason='same-time grouping needed'
            else:status='unknown';reason='canonicalization_or_missing_macro_intent'
        elif not actions:
            status='outside_actor_forced_wait'
        elif until is not None:
            duration=(until-now)/1e9
            if duration>.25:status='unknown';reason='declared_timer_outside_bank_actual_interrupt_unknown'
            elif any(not a['jobs'] and a['wait']==duration for a in actions):status='included_declared_timer'
            else:status='unknown';reason='timer_or_event_interrupt_reachability'
        else:
            status='unknown';reason='undeclared_wait_with_physical_alternative'
        self.records.append(dict(at_ns=now,source_action_kind=kind,source_reason=out.get('reason'),selected=selected,
            source_credit_s=out.get('credit_s'),declared_wait_s=(until-now)/1e9 if until is not None else None,
            status=status,reason=reason,head_ids=sorted(head_ids),new_kinds=[a['kind'] for a in actions],
            scope='pointwise physical bank with upper .25 credit; no full chronological representation proof'))
        return out


def representation_checks(output):
    assert_unconsumed_phase(output, 'representation_before_run.json')
    output=Path(output);budget=Budget(output)
    if (output/'owner.lock').exists():raise ValueError('gate owned')
    lock=output/'owner.lock';lock.write_text(str(os.getpid()),encoding='ascii')
    frozen,case=x.p.inputs(x.p.BUNDLE);initial=case['initial']
    record=dict(status='running',scope='posthoc pointwise source-intent coverage; upper credit is optimistic, not full scheduler replay',
        previous_native_starts=len(budget.rows),registered_contexts=['mean','short_context','long_context'],
        source_sha256=sha(Path(__file__)),cases=[],learning_starts=0,device_commands=0)
    write(output/'representation_before_run.json',record)
    try:
        for context in record['registered_contexts']:
            inner=previous.Controller(frozen,initial,previous.LIST)
            tap=RepresentationTap(inner,frozen,initial)
            item=budget.call('source_intent_'+context,engine,tap,external.old.workload('sustained',812020001),frozen,initial,context)
            old=json.loads(gzip.decompress((output/'items'/('prior_success_'+context+'.json.gz')).read_bytes()))
            for key in ('ledger','transitions','metrics','decisions'):
                if old['result'][key]!=item['result'][key]:raise ValueError('passive tap changed old source '+key)
            counts={status:sum(r['status']==status for r in tap.records) for status in sorted({r['status'] for r in tap.records})}
            record['cases'].append(dict(context=context,source_exact=True,counts=counts,records=tap.records))
        record['status']='completed'
    except BaseException as error:record.update(status='stopped_error',error=repr(error),traceback=traceback.format_exc())
    finally:
        record['consumption']=dict(new_native_environment_starts=len(budget.rows),cumulative_environment_starts=6517+len(budget.rows),
            new_learning_starts=0,cumulative_learning_starts=641,device_commands=0,failed=sum(row['status']=='failed' for row in budget.rows))
        write(output/'representation_checks.json',record)
        if lock.read_text(encoding='ascii')==str(os.getpid()):lock.unlink()
    print(json.dumps(serial(dict(status=record['status'],consumption=record['consumption'],cases=[dict(context=c['context'],counts=c['counts']) for c in record['cases']])),indent=2))
    return record


def run(output):
    torch.set_num_threads(1);torch.manual_seed(11)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    lock=output/'owner.lock';lock.write_text(str(os.getpid()),encoding='ascii')
    budget=Budget(output)
    frozen,case=x.p.inputs(x.p.BUNDLE);initial=case['initial']
    registration=dict(task='LIST-CANDIDATE-RL-IMPLEMENT-04',head=__import__('subprocess').check_output(['git','rev-parse','HEAD'],text=True).strip(),
        recorded_utc=datetime.now(timezone.utc).isoformat(),previous_environment_starts=6517,previous_learning_starts=641,
        max_native_starts=32,new_learning_starts=0,device_commands=0,active_seconds=7200,save_reserve_seconds=300,
        source_hashes={p.as_posix():sha(p) for p in [Path(x.__file__).relative_to(ROOT),Path(engine.__file__).relative_to(ROOT),Path(__file__).relative_to(ROOT)]},
        frozen_model_sha256=x.p.MODEL_SHA,frozen_initial_sha256=x.p.INITIAL_SHA,
        c2_inputs={arm:c2_tickets(frozen,arm) for arm in ('A','B')},c2_continuation=x.GREEDY,
        initial_features=[56,28,8],optional_feature_repair_only_after_alias_evidence=True,
        native_order='legacy nonregression8, C2 four, zero-phase2, neutral development four, known-success replay three, controller variants three',
        experimental_ready=False,original_native_source_sha256=sha(Path(legacy.__file__)))
    write(output/'registration.json',registration)
    summary=dict(status='running',registration=registration,nonregression=[],c2=[],native_gate_pass=False,learning_started=False)
    try:
        small=external.old.workload('low',812010001)[:4]
        factories=[('EDD',lambda:ie.Controller(frozen,initial,'IE_EDD_ECT_LANE_PC_V1')),
                   ('Band',lambda:external.BandController(frozen,initial)),
                   ('Triton',lambda:triton.Controller(frozen,initial,triton.OFF)),
                   ('ListV2',lambda:previous.Controller(frozen,initial,previous.LIST))]
        for name,factory in factories:
            first=budget.call('legacy_'+name,legacy,factory(),small,frozen,initial)
            second=budget.call('fork_'+name,engine,factory(),small,frozen,initial)
            for field in ('ledger','transitions','metrics','decisions'):
                if first['result'][field]!=second['result'][field]:raise ValueError('legacy nonregression '+name+'/'+field)
            summary['nonregression'].append(dict(policy=name,exact_fields=['ledger','transitions','metrics','decisions']))
        cuts={};c2items={}
        for arm in ('A','B'):
            for first in ('C_CPU_NOW','PAIR_NOW'):
                identity='c2_'+arm+'_'+first;script=C2Script(first);c=x.Controller(frozen,initial,selector=script)
                item=budget.call(identity,engine,c,c2_tickets(frozen,arm),frozen,initial)
                if script.cut is None:raise ValueError('registered cut not reached')
                cuts[identity]=abi(script.cut);c2items[identity]=item
                core={row['id']:row.get('response_ns',None)/1e9 if row.get('response_ns') is not None else None for row in item['result']['ledger'] if row['id'] in ('C1','C2','D1')}
                summary['c2'].append(dict(identity=identity,row=item['row'],core_response_s=core,cut=cuts[identity],
                    voluntary_defer_s=c.deferred_seconds,fallbacks=c.fallbacks,selection_opportunities=c.selection_opportunities))
        summary['input_alias']={first:cuts['c2_A_'+first]==cuts['c2_B_'+first] for first in ('C_CPU_NOW','PAIR_NOW')}
        summary['tensor_alias']={first:cuts['c2_A_'+first]['tensors']==cuts['c2_B_'+first]['tensors'] for first in ('C_CPU_NOW','PAIR_NOW')}
        summary['C2_feature_repair_needed']=all(summary['input_alias'].values()) and any(
            c2items['c2_A_PAIR_NOW']['row'][k] > c2items['c2_A_C_CPU_NOW']['row'][k] for k in ('urgent_failure','normal_failure','incomplete'))
        for variant in (x.L0,x.GREEDY):
            c=x.Controller(frozen,initial,variant);item=budget.call('zero_'+variant,engine,c,small[:2],frozen,initial,zero=True)
            if item['row']['completed']!=2 or len(c.responses)!=2:raise ValueError('zero public-event response/request loss')
        summary['behavior']=[]
        for family in ('low','queue','burst','sustained'):
            c=x.Controller(frozen,initial)
            item=budget.call('neutral_'+family,engine,c,external.old.workload(family,812010001),frozen,initial)
            summary['behavior'].append(dict(family=family,row=item['row'],defer_s=c.deferred_seconds,
                holds=c.hold_counter,fallbacks=c.fallbacks,selection_opportunities=c.selection_opportunities,
                forced_waits=c.forced_waits,known_prediction_choices=sum(s['raw'][s['chosen']]['known'] for s in c.snapshots)))
        summary['known_success_replays']=[]
        for context in ('mean','short_context','long_context'):
            c=previous.Controller(frozen,initial,previous.LIST)
            item=budget.call('prior_success_'+context,legacy,c,external.old.workload('sustained',812020001),frozen,initial,context)
            summary['known_success_replays'].append(dict(context=context,row=item['row'],scope='prior development/consumed-final diagnosis only'))
        burst=external.old.workload('burst',812010001)
        network=x.ActorCritic()
        for variant in (x.L0,x.GREEDY,x.PPO):
            c=x.Controller(frozen,initial,variant,network=network if variant==x.PPO else None)
            item=budget.call('variant_'+variant,engine,c,burst,frozen,initial)
            if item['row']['completed']!=len(burst):raise ValueError('variant request loss')
        summary['status']='completed'
        summary['native_gate_pass']=not summary['C2_feature_repair_needed']
    except BaseException as error:
        summary.update(status='stopped_error',error=repr(error),traceback=traceback.format_exc())
    finally:
        summary['consumption']=dict(new_native_environment_starts=len(budget.rows),failed=sum(r['status']=='failed' for r in budget.rows),
            cumulative_environment_starts=6517+len(budget.rows),new_learning_starts=0,cumulative_learning_starts=641,device_commands=0)
        summary['executions']=budget.rows
        write(output/'summary.json',summary)
        if lock.read_text(encoding='ascii')==str(os.getpid()):lock.unlink()
    print(json.dumps(serial(summary),ensure_ascii=False,indent=2))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--additional',action='store_true');parser.add_argument('--representation',action='store_true')
    args=parser.parse_args()
    result = representation_checks(args.output) if args.representation else additional_checks(args.output) if args.additional else run(args.output)
    raise SystemExit(0 if result['status'] == 'completed' else 1)
