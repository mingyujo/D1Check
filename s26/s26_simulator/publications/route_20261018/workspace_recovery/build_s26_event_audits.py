"""Saved-only audits for event waits, causal preferences, BC and true PPO."""
from pathlib import Path
W=Path(__file__).resolve().parent.parent;P=W/'S26-D1Check/s26_simulator/experiments/route_energy_v1';H=P.parent/'route_event_learning_v1'
s=(P/'audit.cjs').read_text(encoding='utf-8').replace('420','134')
extra="""
let eventActions=0,preferenceAssignments=0;
function eventAudit(row,raw){
 let dose=0;const planned=new Map(raw.planned_requests.map(q=>[q.ordinal,q]));
 for(const d of raw.policy_decisions){
  if(d.action.kind==='WAIT')dose+=d.action.wait_s;
  if(d.action.kind==='WAIT_EVENT'){
   eventActions++;need(Number.isFinite(d.wait_end)&&d.wait_end>=d.time-1e-9,'Event wait endpoint');dose+=d.wait_end-d.time;
   const owners=raw.requests.filter(q=>q.route&&q.times.dispatch<=d.time+1e-9&&(q.available===null||q.available>d.time+1e-9));
   const expected=Math.min(raw.dispatch_stop_s,...owners.map(q=>q.available??raw.observation_end_s),...raw.planned_requests.filter(q=>q.readyAt>d.time+1e-9).map(q=>q.readyAt));
   need(owners.length>0||d.wait_end-d.time<1e-8,'Event requires active work');need(Math.abs(d.wait_end-expected)<1e-7,'Wait ends at first observable ready/release/dispatch-stop event');
  }
 }
 need(Math.abs(dose-row.wait_s)<1e-6,'Fixed/event wait total');
 const ctx=raw.route_context_evidence;if(!ctx)return;
 const seen=new Set;for(const t of ctx.task_seen){need(!seen.has(t.ordinal),'Unique public task observation');seen.add(t.ordinal);need(planned.get(t.ordinal).readyAt<=t.time+1e-8,'No future task visibility');need(planned.get(t.ordinal).task===t.task,'Observed task identity');}
 let classes=0;const assigned=new Set;
 for(const p of ctx.preferences){
  preferenceAssignments++;need(!assigned.has(p.ordinal),'Unique preference assignment');assigned.add(p.ordinal);
  const history=ctx.task_seen.filter(t=>t.time<=p.time+1e-9).slice(-64),mix=history.length<16?.75:history.filter(t=>t.task==='classification').length/history.length;
  need(history.some(t=>t.ordinal===p.ordinal)||ctx.task_seen.some(t=>t.ordinal===p.ordinal&&t.time<=p.time+1e-9),'Preference after public observation');need(p.seen_count===history.length&&Math.abs(p.observed_mix-mix)<1e-10,'Causal recent64 mix');
  let expected='detection_CPU';if(planned.get(p.ordinal).task==='classification'){expected=mix<=.625?'classification_NPU':classes%4===3?'classification_GPU':'classification_NPU';classes++;}
  need(p.route===expected&&p.class_counter===classes,'Causal preference feature, no deadline input');
 }
}
"""
s=s.replace('for(const row of result.rows){',extra+'\nfor(const row of result.rows){',1)
s=s.replace(" if((result.rows.indexOf(row)+1)%50===0)"," eventAudit(row,raw);\n if((result.rows.indexOf(row)+1)%50===0)",1)
s=s.replace('max_actual_CPU_grants:maxGrant,','max_actual_CPU_grants:maxGrant,event_wait_actions:eventActions,causal_preference_assignments:preferenceAssignments,')
(H/'audit.cjs').write_text(s,encoding='utf-8')
s=(P/'audit_nn.py').read_text(encoding='utf-8')
s=s.replace("logits=np.where(mask,logits,-1e9);lp=", "logits=logits/getattr(net,'temperature',1.);logits=np.where(mask,logits,-1e9);lp=",1)
start=s.index("    for model in ['CENTRAL','CPU3']:");end=s.index('    nets={}',start)
new="""    from bc import teacher,pretrain
    demonstrations=[]
    for row in [r for r in result['rows'] if r['kind']=='DEMO']:
        data=load(O/(row['label']+'.demonstrations.pt.gz'));demonstrations.append(data);raw=read(O/(row['label']+'.raw.json.gz'));need(len(raw['policy_decisions'])==len(data['frames']),'All teacher decisions recorded')
        for f,d in zip(data['frames'],raw['policy_decisions']):
            need(f['from_teacher'] and not f['collect'],'Declared demonstration, not PPO');need(teacher(dict(x=f['x'],mask=f['mask'],actions=f['candidate_actions']))==f['index'],'Reproducible public teacher')
            for k in ['kind','ordinal','route','wait_s']:need(f['action'].get(k)==d['action'].get(k),'Actual teacher action binding')
    parent=load(op['parent_checkpoint']);warm,bc_trace=pretrain(parent,demonstrations,op['BC_seed']);saved_trace=load(O/'BC_TRACE.pt.gz');equal(bc_trace,saved_trace);equal(warm.snapshot(),load(O/'BC_COMMON_FINAL.pt.gz')['learner']);bc_steps=bc_trace['steps'];del demonstrations
    for seed in op['seeds']:
        learner=Learner(seed);learner.restore(load(O/f'S{seed}_EP000.pt.gz'));need(learner.net.temperature==.35,'Sampling/PPO temperature recorded');order=read(O/f'S{seed}_ORDER.json');need(order['order']==np.random.default_rng(seed+50000).permutation(8).tolist(),'Fresh case RNG')
        for ep in range(1,9):
            prefix=f'S{seed}_EP{ep:03d}';before=load(O/(prefix+'_before.pt.gz'));after=load(O/(prefix+'_after.pt.gz'));equal(learner.snapshot(),before['learner']);learner.balance=copy.deepcopy(before['balance'])
            row=read(O/('TRAIN_'+prefix+'.json'));data=load(O/(row['label']+'.frames.pt.gz'));forward(data['frames'],learner.net,row)
            need(np.max(abs(data['physical_costs'].sum(0)-row['balanced_cost']))<1e-7,'Balanced reward telescope')
            expected=data['physical_costs'].copy();expected[:,0]/=data['balance']['scales'][0];expected[:,1]/=data['balance']['scales'][1];expected[:,2]*=data['balance']['classFactors'][0];expected[:,3]*=data['balance']['classFactors'][1];need(np.max(abs(expected-data['learning_costs']))<1e-12,'Declared objective normalization')
            for f in data['frames']:
                index,replay=learner.choose(dict(x=f['x'],mask=f['mask'],scores=f['scores']),True);need(index==f['index'] and abs(replay['old_logp']-f['old_logp'])<1e-7,'Exact temperature-scaled action RNG')
            old=learner.updates;learner.add(data['frames'],data['learning_costs']);equal(learner.snapshot(),after['learner']);updates+=learner.updates-old
        need(learner.updates==4,'Four PPO updates per seed');print('EVENT_SAVED_NN_REPLAY',seed,flush=True)
"""
s=s[:start]+new+s[end:]
old="s=load(op['parent_checkpoint']) if row['seed']==481083 else load(O/f'{row[\"model\"]}_S{row[\"seed\"]}_FINAL.pt.gz')['learner']"
new="s=load(op['parent_checkpoint']) if row['seed']==481083 else load(O/'BC_COMMON_FINAL.pt.gz')['learner'] if row['seed']==781000 else load(O/f'S{row[\"seed\"]}_FINAL.pt.gz')['learner']"
assert s.count(old)==1;s=s.replace(old,new)
s=s.replace("need(updates==48,'All48 updates replayed')", "need(updates==12,'All12 PPO updates replayed')")
s=s.replace('replayed_updates=updates,actual_overdue', 'replayed_updates=updates,replayed_BC_steps=bc_steps,actual_overdue')
s=s.replace("WAIT_actions=sum(f['action']['kind']=='WAIT' for f in frames)","WAIT_actions=sum(f['action']['kind']=='WAIT' for f in frames),WAIT_EVENT_actions=sum(f['action']['kind']=='WAIT_EVENT' for f in frames)")
# Check the new preference/event plane only for the unprotected new branch.
needle="                if not f['collect']:need(int(logits[i].argmax())==f['index'],'Exact neural final choice')"
replacement="""                if row['balanced']:
                    pref={p['ordinal']:p['route'] for p in raw['route_context_evidence']['preferences']}
                    for j,a in enumerate(f['candidate_actions']):
                        expected=-1 if a['kind']=='WAIT_EVENT' else int(a['kind']=='DISPATCH' and a.get('route')==pref[a['ordinal']]);need(float(f['x'][j,31])==expected,'Actual causal preference/event feature')
                if not f['collect']:need(int(logits[i].argmax())==f['index'],'Exact neural final choice')"""
assert s.count(needle)==1;s=s.replace(needle,replacement)
compile(s,str(H/'audit_nn.py'),'exec');(H/'audit_nn.py').write_text(s,encoding='utf-8');print('EVENT_SAVED_PHYSICS_CONTEXT_WAIT_BC_AND_PPO_AUDITS_READY')
