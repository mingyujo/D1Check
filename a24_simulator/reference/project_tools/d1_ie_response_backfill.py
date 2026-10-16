"""EDD head GPU-now exception guarded by full arrived-queue response projection."""
from tools import d1_ie_priority_compare as base
p=base.p
POLICY='IE_EDD_GPU_RESPONSE_NONWORSE_PC_V1'
class Controller(base.Controller):
    def __init__(self,frozen,initial):
        super().__init__(frozen,initial,'EDD');self.public_policy=POLICY;self.corrections=0
    def project(self,ordered,active,first,now):
        jobs=[dict(j) for j in active]+[first];responses={first['id']:first['response']};earliest=first['start']
        for q in ordered[1:]:
            choices=[self.place(q,b,earliest,jobs) for b in p.backends(q)]
            chosen=min(choices,key=lambda j:(j['end'],j['backend']!='CPU'))
            jobs.append(chosen);responses[q['id']]=chosen['response'];earliest=chosen['start']
        return responses
    def decide(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        out=super().decide(config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        out['public_policy']=POLICY
        if out['reason']!='ECT_wait_for_best_resource' or out['chosen_backend']!='CPU':return out
        head=next(q for q in queue if q['id']==out['head_request_id'])
        if head['task']!='classification' or lanes['GPU']['request'] is not None:return out
        owner=lanes['CPU']['request']
        if not owner or owner['task']!='detection':return out
        now=now_ns/1e9;active=self.active_jobs(lanes,now)
        if active is None:return out
        gpu=self.place(head,'GPU',now,active);cpu=next(j for j in out['candidates'] if j['backend']=='CPU')
        if gpu['start']>now or gpu['response']>cpu['response']:return out
        by_id={q['id']:q for q in queue};ordered=[by_id[i] for i in out['ordered_ids']]
        prior=self.project(ordered,active,cpu,now);changed=self.project(ordered,active,gpu,now)
        allowed=all(changed[i]<=prior[i] for i in prior)
        out['response_guard']=dict(allowed=allowed,baseline=prior,alternative=changed,
            future_arrivals_used=False,all_arrived_responses_nonworse=allowed,performance_guarantee=False)
        if not allowed:return out
        p.state(['detection_CPU','classification_GPU']);self.corrections+=1
        out.pop('wait_until_ns',None)
        out.update(selected=dict(request_id=head['id'],backend='GPU'),reason=POLICY,chosen_backend='GPU',
            planned_start_s=gpu['start'],predicted_response_s=gpu['response'],predicted_lane_end_s=gpu['end'])
        return out
