"""Saved-only same-request outcomes and previous low-load examples."""
import collections,hashlib,json
import study as S
H,R,O=S.H,S.R,S.O
inputs=S.read(H/'INPUTS.json');rows=S.read(O/'RESULT.json')['rows'];out=[]
digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
for row in rows:
    if row['kind']!='EVAL' or row['status']!='COMPLETE':continue
    d=S.read(R/row['raw']['path']);target={q['request_id']:q for q in d['result']['requests']};targetActions=digest([x['action'] for x in d['result']['decisions']]);targetTrace=digest(d['result']['trace']);comp=[]
    for policy in ('FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_FAIR','BC_NEURAL_PREVIOUS','BC_OLD'):
        reference=next(r for r in inputs['comparators'] if r['case']==row['case'] and r['policy']==policy);raw=S.read(R/reference['raw']['path'])['result'];ref={q['request_id']:q for q in raw['requests']};counts=collections.Counter();examples=[]
        for rid,q in target.items():
            old=ref[rid];assert all(q[k]==old[k] for k in ('scheduled_arrival_ns','queue_entry_ns','deadline_ns','priority','task'))
            before=old['response_ns'] is not None and old['response_ns']<=old['deadline_ns'];after=q['response_ns'] is not None and q['response_ns']<=q['deadline_ns']
            if before!=after:counts[q['priority']+('_gained_on_time' if after else '_lost_on_time')]+=1
            if rid in ('common-000396','common-000255','common-000528') and row['case'].endswith('R1_burst'):
                examples.append(dict(id=rid,priority=q['priority'],task=q['task'],deadline_s=q['deadline_ns']/1e9,reference_on_time=before,new_on_time=after,reference_dispatch_s=old['dispatch_ns']/1e9,new_dispatch_s=q['dispatch_ns']/1e9,reference_response_s=old['response_ns']/1e9,new_response_s=q['response_ns']/1e9,reference_route=old['route'],new_route=q['route']))
        identical=raw['requests']==list(target.values()) and targetActions==digest([x['action'] for x in raw['decisions']]) and targetTrace==digest(raw['trace'])
        comp.append(dict(reference=policy,counts=dict(counts),requests_actions_trace_exact=identical,previous_lowload_examples=examples));del raw
    out.append(dict(case=row['case'],comparisons=comp));print('SAVED_MATCHED',row['case'],flush=True)
S.new(O/'MATCHED_REQUESTS.json',dict(status='PASS',rows=out,new_environment=0,new_fit=0,scope='Saved trajectories and matched requests; no single-action causal intervention'))
