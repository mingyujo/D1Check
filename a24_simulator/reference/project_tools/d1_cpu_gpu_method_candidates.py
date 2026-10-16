"""Separate physical-mask energy candidate. Original C and plant stay intact."""
from __future__ import annotations
import copy
import math
import numpy as np
import torch
from tools import d1_edd_ect_residual_ppo as current

core=current.core
ENERGY_RULE='EDD_ECT_ENERGY_AP_GUARD_PC_V1'
ENERGY_RL='EDD_ECT_PHYSICAL_MASK_ENERGY_PPO_PC_V1'


class CurrentController(current.Controller):
    """C input hotfix only; source fallback behavior/optimizer stay unchanged."""
    def decide(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        try:return super().decide(config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        except KeyError as error:
            if error.args!=('state_features',):raise
            reply=self.last_reply
            if not reply or not reply.get('forced') or reply.get('reason')!='unavailable_forecast_exact_base':raise
            state,_=self.tensors(queue,lanes,now_ns,[])
            obs=np.asarray(state,dtype=np.float32);cand=np.zeros((32,68),dtype=np.float32)
            mask=np.zeros(32,dtype=bool);mask[0]=True;bases=np.zeros(32,dtype=bool)
            with torch.no_grad():
                _,value=self.network(torch.from_numpy(obs)[None],torch.from_numpy(cand)[None],torch.from_numpy(mask)[None],torch.from_numpy(bases)[None])
            self.trajectory.append(dict(t_s=now_ns/1e9,state=obs,candidates=cand,mask=mask,base=bases,action=0,
                logprob=0.,value=value[0].numpy(),informative=False,grid_peak=max(self.grid.values()) if self.grid else None))
            out={k:v for k,v in reply.items() if k not in ('candidates','state_features','candidate_features')}
            out['public_policy']=self.public_policy;out['input_hotfix']='forced_base_schema'
            self.last_reply=copy.deepcopy(out)
            return out


class Controller(core.Controller):
    def __init__(self,frozen,initial,network=None,deterministic=False,*,no_wait=False,no_heat=False):
        super().__init__(frozen,initial,core.PRIOR,record_forecasts=False)
        self.public_policy=ENERGY_RL if network is not None else ENERGY_RULE
        self.network=network;self.deterministic=deterministic;self.trajectory=[]
        self.no_wait=no_wait;self.no_heat=no_heat

    def physical(self,queue,lanes,now_ns,base):
        if base['selected']:actions=[dict(kind='single',jobs=[base['selected']],base=True)]
        else:actions=[dict(kind='ect_resource_wait' if base.get('wait_until_ns') else 'event_wait',jobs=[],base=True,
                          **({'wait_until_ns':base['wait_until_ns']} if base.get('wait_until_ns') else {}))]
        members=[l['request']['task']+'_'+b for b,l in lanes.items() if l['request']]
        ordered=sorted(queue,key=core.due)[:8]
        for q in ordered:
            for backend in core.p.backends(q):
                if lanes[backend]['request'] is not None:continue
                try:core.p.state(members+[q['task']+'_'+backend])
                except ValueError:continue
                actions.append(dict(kind='single',jobs=[dict(request_id=q['id'],backend=backend)],base=False))
        if not any(l['request'] for l in lanes.values()):
            for c in ordered:
                if c['task']!='classification':continue
                for d in ordered:
                    if d['task']!='detection':continue
                    actions.append(dict(kind='bundle',base=False,jobs=[dict(request_id=q['id'],backend='GPU' if q['task']=='classification' else 'CPU') for q in sorted((c,d),key=core.due)]))
        delay=min(self.credit,120.-now_ns/1e9)
        if not self.no_wait and any(a['jobs'] for a in actions) and delay>1e-9:
            actions.append(dict(kind='cool_wait',jobs=[],base=False,wait_until_ns=now_ns+delay*1e9))
        unique={}
        for a in actions:
            key=core.signature(a)
            if key not in unique:unique[key]=a
            else:unique[key]['base']|=a['base']
        assert len(unique)<=30
        return list(unique.values())

    def feature_vectors(self,queue,lanes,now_ns,actions):
        # Unknown ECT placement is a feature validity state, never a zero cost.
        unavailable=self.active_jobs(lanes,now_ns/1e9) is None
        masked=[dict(a,jobs=[]) for a in actions] if unavailable else actions
        state,vectors=self.tensors(queue,lanes,now_ns,masked)
        if unavailable:
            schema=core.json.loads((core.p.ROOT/'docs/results/edd_ect_residual_design_01/design_contract.json').read_text(encoding='utf8'))['observation']
            indices={field:i for i,field in enumerate(schema['candidate_fields'])}
            ordered=sorted(queue,key=core.due);by={q['id']:q for q in ordered};ranks={q['id']:i for i,q in enumerate(ordered)}
            for a,v in zip(actions,vectors):
                for j,job in enumerate(a['jobs']):
                    q=by[job['request_id']];prefix=f'job_{j}.'
                    fields=dict(present=1.,classification=float(q['task']=='classification'),detection=float(q['task']=='detection'),
                        urgent=float(q['priority']=='urgent'),normal=float(q['priority']=='normal'),CPU=float(job['backend']=='CPU'),GPU=float(job['backend']=='GPU'),
                        age_over_2s=(now_ns-q['arrival_ns'])/2e9,slack_over_own_deadline=(q['arrival_ns']+q['deadline_offset_ns']-now_ns)/q['deadline_offset_ns'],
                        edd_rank_over_192=ranks[q['id']]/192,is_ect_backend=-1.,ect_lane_excess_over_6s=0.)
                    for field,value in fields.items():v[indices[prefix+field]]=value
        if self.no_heat:
            schema=core.json.loads((core.p.ROOT/'docs/results/edd_ect_residual_design_01/design_contract.json').read_text(encoding='utf8'))['observation']
            for i,name in enumerate(schema['state_fields']):
                if 'modeled_ap' in name or 'modeled_h' in name or 'modeled_grid' in name or name=='has_modeled_grid_sample':state[i]=0.
            for vector in vectors:
                for i,name in enumerate(schema['candidate_fields']):
                    if 'delta_grid_peak' in name:vector[i]=0.
        return state,vectors

    def decide(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now_ns)
        if self.pending:
            pending,self.pending=self.pending,None
            first,second=pending['first'],pending['second']
            if (now_ns==pending['now_ns'] and lanes[first['backend']]['request'] and
                lanes[first['backend']]['request']['id']==first['request_id'] and lanes[second['backend']]['request'] is None
                and any(q['id']==second['request_id'] for q in queue)):
                return dict(now_ns=now_ns,selected=second,reason='bundle_commit',action_kind='bundle_commit')
            self.cancelled_bundles+=1
        key=core.public_signature(queue,lanes,now_ns)
        if key==self.last_signature:return copy.deepcopy(self.last_reply)
        base=core.ie.Controller.decide(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        if not queue:return base
        actions=self.physical(queue,lanes,now_ns,base)
        original=actions[0]
        for a in actions:a['forecasts']={ctx:self.forecast(queue,lanes,now_ns,a,ctx) for ctx in core.CONTEXTS}
        original_forecasts=original['forecasts']
        for a in actions:
            for ctx,f in a['forecasts'].items():
                f['calculation_valid']=f['valid']
                if f['valid'] and original_forecasts[ctx]['valid']:
                    f['delta_j']=f['remaining_increment_j']-original_forecasts[ctx]['remaining_increment_j']
                    f['delta_ap']=f['peak_ap_c']-original_forecasts[ctx]['peak_ap_c']
                else:f['valid']=False
            a['valid']=True # generated physical feasibility only
        merged={}
        for a in actions:
            fingerprint=(tuple(tuple((j['request_id'],j['backend'],j['at_ns']) for j in a['forecasts'][ctx]['dispatches']) for ctx in core.CONTEXTS)
                         if all(f['valid'] for f in a['forecasts'].values()) else ('unknown',core.signature(a)))
            if fingerprint not in merged:merged[fingerprint]=a
            else:merged[fingerprint]['base']|=a['base']
        actions=list(merged.values())
        original=next(a for a in actions if a['base'])
        state,vectors=self.feature_vectors(queue,lanes,now_ns,actions)
        if self.network is None:
            safe=[a for a in actions if all(f['valid'] and f['feasible'] and f['delta_ap']<=1e-9 for f in a['forecasts'].values())]
            chosen=min(safe,key=lambda a:(max(f['delta_j'] for f in a['forecasts'].values()),max(f['delta_ap'] for f in a['forecasts'].values()),not a['base'],actions.index(a))) if safe else original
        else:
            obs=np.asarray(state,dtype=np.float32);cand=np.asarray(vectors+[[0.]*68]*(32-len(vectors)),dtype=np.float32)
            mask=np.asarray([True]*len(actions)+[False]*(32-len(actions)),dtype=bool)
            bases=np.asarray([a['base'] for a in actions]+[False]*(32-len(actions)),dtype=bool)
            with torch.no_grad():
                dist,value=self.network(torch.from_numpy(obs)[None],torch.from_numpy(cand)[None],torch.from_numpy(mask)[None],torch.from_numpy(bases)[None])
                informative=len(actions)>1
                action=dist.probs.argmax(-1) if self.deterministic or not informative else dist.sample()
                index=int(action);chosen=actions[index]
                self.trajectory.append(dict(t_s=now_ns/1e9,state=obs,candidates=cand,mask=mask,base=bases,action=index,
                    logprob=float(dist.log_prob(action)),value=value[0].numpy(),informative=informative,
                    grid_peak=max(self.grid.values()) if self.grid else None))
        out=self._reply(chosen,now_ns)
        out.update(public_policy=self.public_policy,chosen_base=chosen['base'],valid_actions=len(actions),credit_s=self.credit,
            forecast_supported=all(f['valid'] for f in chosen['forecasts'].values()),modeled_ap_c=self.t)
        self.actions.append(copy.deepcopy(out));self.last_signature=key;self.last_reply=copy.deepcopy(out)
        return out


def targets(controller,row,references):
    """Separate ENERGY_AP_NONWORSE_V1; six heads, same PPO/update settings."""
    data,_,valid=current.target_data(controller,row,references)
    costs=np.zeros(5,dtype=np.float64)
    costs[1]=row['planned']-row['completed']
    if row['peak_ap_c'] is not None and all(r['peak_ap_c'] is not None for r in references):
        costs[0]=max(0.,*(row['peak_ap_c']-r['peak_ap_c']-1e-9 for r in references))
    else:valid[1]=False
    for i,key,scale in [(2,'urgent_service_failure',1.),(3,'normal_service_failure',1.),(4,'urgent_p95_ms',1500.)]:
        if row.get(key) is not None and all(r.get(key) is not None for r in references):costs[i]=max(0.,*(row[key]-r[key]-(1e-9 if i==4 else 0.) for r in references))/scale
        else:valid[i+1]=False
    full=row['completed']==row['planned'] and all(r['completed']==r['planned'] for r in references)
    valid[0]=full
    # Running intervals are explicitly accounted in the frozen whole-window J.
    # Terminal MC reward has gamma=1, so extra events/waits cannot earn a bonus.
    gain=references[0]['energy_j']-row['energy_j'] if full else 0.
    for step in data:
        step['target']=np.asarray([gain,*costs],dtype=np.float32);step['valid']=valid.copy()
    return data,costs,valid
