"""Same BC50 actor, public deadline-bounded WAIT protection before shared mask."""
import numpy as np
from a24_nn_urgent_tie_20261021.policy import Policy as OldPolicy
from a24_nn_margin_exact_20261021.policy import relative_cost
VERSION='A24_BC50_S26_MATCHED_LATEST_START_WAIT_V5'

def protect_waits(s,b,risk,tick):
    original=np.asarray(b['idle_mask'],bool);allowed=original.copy();lookup={q['request_id']:q for q in s['queue']};slack={};routes={}
    for i,a in enumerate(b['actions']):
        if not original[i] or a['kind']!='DISPATCH':continue
        q=lookup[a['request_id']]
        if q['priority']!='U':continue
        end=b['forecasts'][i]['responses_s'].get(q['request_id'],b['forecasts'][i]['H_s']);v=q['deadline_ns']/1e9-end-risk[q['task']]
        if q['request_id'] not in slack or v>slack[q['request_id']]:slack[q['request_id']]=float(v);routes[q['request_id']]=i
    blocked=[];reasons=[]
    for i,a in enumerate(b['actions']):
        if not allowed[i] or a['kind']=='DISPATCH':continue
        wait=a.get('wait_ns',a.get('max_wait_ns',0))/1e9;critical=[rid for rid,v in slack.items() if v<=wait+tick+1e-8]
        if critical:allowed[i]=False;blocked.append(i);reasons.append({'index':i,'wait_bound_s':wait,'critical_ready_urgent_ids':critical})
    assert allowed.any()
    return allowed,{'rule':'exclude WAIT when an eligible urgent dispatch latest-start slack <= wait upper bound + tick','blocked_wait_indices':blocked,'reasons':reasons,'urgent_slack_s':slack,'fastest_dispatch_indices':routes,'tick_s':tick,'future_information':False}

class Policy(OldPolicy):
    def encode(self,s):
        b=super().encode(s);gate,record=protect_waits(s,b,self.risk,self.physics.c.tick_s);allowed=np.flatnonzero(gate);best=min(tuple(b['risk_pairs'][i]) for i in allowed);mask=np.zeros(36,bool)
        for i in allowed:mask[i]=tuple(b['risk_pairs'][i])==best
        forced=[r['index'] for r in b['service_guard']['critical_normal'] if mask[r['index']]]
        if forced:mask[:]=False;mask[forced]=True
        b['mask']=mask;b['deadline_wait_guard']=record;b['guard_mask']=gate;b['risk_guard']=dict(b['risk_guard'],best=list(best),priority='deadline WAIT guard, buffered urgent late, nominal total late, nominal urgent late');b['service_guard']=dict(b['service_guard'],forced_normal_indices=forced);b['x'][:,28],b['cost_normalization']=relative_cost(b['teacher_scores'],mask)
        return b
    def __call__(self,s):
        action=super().__call__(s);self.calls[-1]['version']=VERSION
        if self.collect:self.frames[-1]['teacher_version']=VERSION;self.frames[-1]['guard_fired']=bool(self.calls[-1]['deadline_wait_guard']['blocked_wait_indices']);self.frames[-1]['chosen_differs_teacher']=self.calls[-1]['chosen']!=self.calls[-1]['teacher_index']
        return action
