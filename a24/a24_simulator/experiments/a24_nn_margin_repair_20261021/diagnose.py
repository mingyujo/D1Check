"""Saved-state diagnosis before registering a new experiment, no fit/environment."""
import math
from pathlib import Path
import sys
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H.parent))
from a24_fair_nn_bc_20261021 import study as S
from a24_nn_margin_repair_20261021.policy import relative_cost
np=S.np
def stats(v):
    v=sorted(v);return dict(n=len(v),median=v[len(v)//2] if v else None,P95=v[math.ceil(.95*len(v))-1] if v else None,max=max(v) if v else None)
rows=[]
for row in S.read(S.O/'RESULT.json')['rows']:
    if row['kind']!='EVAL':continue
    d=S.read(S.R/row['raw']['path']);oldgap=[];z_gap=[];other=[];sequence=[]
    for dec,c in zip(d['result']['decisions'],d['calls']):
        i,t=c['chosen'],c['teacher_index'];mask=np.asarray(c['mask'],bool);scores=np.asarray(c['teacher_scores']);z,norm=relative_cost(scores,mask)
        if not c['teacher_mask'][i]:
            x=np.asarray(c['x']);oldgap.append(abs(float(x[i,28]-x[t,28])));z_gap.append(abs(float(z[i]-z[t])));other.append(float(np.linalg.norm(np.delete(x[i]-x[t],28))))
        if row['case'].endswith('R1_burst') and any(q['request_id']=='common-000396' for q in dec['public_state']['queue']):
            candidate=[dict(index=j,action=a,allowed=c['mask'][j],cost=scores[j],absolute_input=c['x'][j][28],relative_input=float(z[j])) for j,a in enumerate(c['actions']) if a.get('request_id')=='common-000396']
            sequence.append(dict(time_s=c['time_ns']/1e9,action=c['action'],teacher_action=c['actions'][t],candidates=candidate))
    rows.append(dict(case=row['case'],mismatch_score_feature_gap=stats(oldgap),same_information_normalized_gap=stats(z_gap),other_feature_vector_distance=stats(other),lowload_same_request_decisions=sequence));print('PRECHANGE_DIAG',row['case'],stats(oldgap),stats(z_gap),flush=True)
S.new(H/'PRECHANGE_DIAG.json',dict(status='SAVED_DIAGNOSIS_ONLY',rows=rows,new_environment=0,new_fit=0,EVAL_used_for_gradient=False,scope='Representation magnitude and saved decisions; paired TRAIN fit will test the normalization effect, no standalone causal claim'))
