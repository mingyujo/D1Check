"""Saved-only remaining exact-action errors and contradictory float32 inputs."""
import collections,hashlib
import study as S
H,R,O=S.H,S.R,S.O
result=S.read(O/'RESULT.json');frames=S.loadpt(O/'TRAIN_DATASET.pt.gz')['frames'];state=S.loadpt(R/result['fits'][-1]['checkpoint']['path']);net=S.Learner(state=state);before=net.snapshot();groups=collections.defaultdict(collections.Counter);errors=[]
for start in range(0,len(frames),128):
    part=frames[start:start+128];x=S.np.stack([f['x'] for f in part]);m=S.np.stack([f['mask'] for f in part])
    with S.torch.no_grad():p=net.net(S.torch.from_numpy(x),S.torch.from_numpy(m))[0].argmax(-1).numpy()
    for j,f in enumerate(part):
        key=hashlib.sha256(f['x'].tobytes()+f['mask'].tobytes()).hexdigest();groups[key][f['index']]+=1
        if int(p[j])!=f['index']:
            i=int(p[j]);t=f['index'];errors.append(dict(source=f['source_raw'],case=f['source_case'],decision=f['source_decision_index'],teacher_index=t,chosen=i,teacher_score=float(f['scores'][t]),chosen_score=float(f['scores'][i]),teacher_input28=float(f['x'][t,28]),chosen_input28=float(f['x'][i,28]),cost_compatible=bool(f['cost_compatible_mask'][i])))
contradictory=[dict(input_sha=k,labels=dict(v),rows=sum(v.values())) for k,v in groups.items() if len(v)>1]
eva=[]
for row in result['rows']:
    if row['kind']!='EVAL':continue
    d=S.read(R/row['raw']['path']);count=collections.Counter()
    for c in d['calls']:
        if c['chosen']==c['teacher_index']:continue
        i,t=c['chosen'],c['teacher_index'];regret=c['teacher_scores'][i]-min(v for v,m in zip(c['teacher_scores'],c['mask']) if m);count['exact_mismatch']+=1;count['cost_compatible_tie']+=c['cost_compatible_mask'][i];count['regret_le_1e-3']+=regret<=1e-3;count['regret_le_1e-2']+=regret<=1e-2;count['normalized_score_float32_equal']+=c['x'][i][28]==c['x'][t][28]
    eva.append(dict(case=row['case'],counts=dict(count)))
S.equal(net.snapshot(),before)
S.new(O/'REMAINING_ERROR_AUDIT.json',dict(status='PASS',TRAIN_errors=errors,contradictory_identical_float32_input_groups=contradictory,contradiction_lower_bound_errors=sum(x['rows']-max(x['labels'].values()) for x in contradictory),EVAL=eva,scope='Saved exact teacher labels, full float32 input hashes and deterministic forward inference; no new fit or environment',new_environment=0,new_fit=0))
print('REMAINING_ERRORS',len(errors),'TRAIN; conflicting identical input groups',len(contradictory),eva,flush=True)
