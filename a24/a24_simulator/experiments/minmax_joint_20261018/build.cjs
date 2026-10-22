'use strict';
const fs=require('fs'),path=require('path'),d=__dirname,parent=path.resolve(d,'../queue_context_20261018');let run=fs.readFileSync(path.join(parent,'run.py'),'utf8');
function replace(a,b){if(!run.includes(a))throw Error('Minmax run anchor '+a.slice(0,100));run=run.replace(a,b);}
replace("from queue_controller import QueueContextController as PublicController","sys.path.insert(0,str(HERE.parent/'queue_context_20261018'))\nfrom queue_controller import QueueContextController as PublicController\nfrom minmax_labels import labels as joint_labels");
replace("B.G.OWN_TOKENS+=('queue_context_20261018',)","B.G.OWN_TOKENS+=('minmax_joint_20261018',)");
const bc="    before=loadpt(out/'BC_BEFORE.pt.gz');data=loadpt(out/'BC_DATA.pt.gz');l=Learner(before);l.distill(data['x'],data['mask'],data['teacher']);equal(l.snapshot(),loadpt(out/'BC_AFTER.pt.gz'))\n";replace(bc,'');
replace("            if row['kind']=='P0':l=B.Learner(state['seed']);l.restore(state)\n            else:l=Learner(state)","            l=Learner(state)");
replace('BC_epochs=64,BC_exact_optimizer_replay=True','BC_epochs=0,BC_exact_optimizer_replay=False,reused_frozen_BC_warm=True');
replace("if p0:actor=B.GuardController(nominal,physics,case,'RL',learner,False,deadline_guard=True)","if p0:actor=PublicController(nominal,physics,case,'RL',learner,False,deadline_guard=False)");
replace("costs,audit=(B.original_rewards.labels(result,actor.frames,case,physics,metrics) if p0 else B.repaired_labels(result,actor.frames,case,physics,metrics,references[case['id']]))","costs,audit=joint_labels(result,actor.frames,case,physics,metrics,references[case['id']],op['reward_references'][case['id']])");
replace("network_temperature=(1. if p0 else learner.temperature) if neural else None,reward_kind='ORIGINAL' if p0 else 'REPAIRED'","network_temperature=learner.temperature if neural else None,reward_kind='MINMAX_JOINT'");
replace("initial=loadpt(op['checkpoint']['path']);frozen=B.Learner(op['learner_seed']);frozen.restore(copy.deepcopy(initial));pt(out/'P0_INITIAL.pt.gz',frozen.snapshot())","initial=loadpt(op['warm_checkpoint']['path']);frozen=Learner(copy.deepcopy(initial));pt(out/'P0_INITIAL.pt.gz',frozen.snapshot())");
replace("simulate(case,'P0_ORIGINAL_NN','P0'","simulate(case,'P0_WARM_CONTEXT_NN','P0'");
const begin=run.indexOf('            for case in training:'),end=run.indexOf('            for arm,l in arms.items():',begin);if(begin<0||end<0)throw Error('Warm reuse block');
run=run.slice(0,begin)+`            improved=Learner(copy.deepcopy(initial),anchor=True);arms=dict(MINMAX_CONTEXT_OFF=improved);initials={k:digest(l.net) for k,l in arms.items()};teacher='REUSED_CONTEXT_BC_WARM'
            equal(improved.snapshot(),loadpt(op['paired_initial_snapshot']['path']))
            B.G.write_new(out/'TEACHER_SELECTION.json',dict(teacher=teacher,new_BC_epochs=0,evaluation_used=False,warm_checkpoint_sha256=op['warm_checkpoint']['sha256']))
`+run.slice(end);
replace("new_Adam_steps=2*(l.steps-initial['steps'])+l.bc_steps","new_Adam_steps=2*(l.steps-initial['steps'])");
replace("bc_steps=l.bc_steps,logs=l.logs","bc_steps=0,reused_BC_steps=l.bc_steps,logs=l.logs");
replace("                for ep in range(32):simulate(training[ep%8],arm,'TRAIN',arm+f'_TRAIN_{ep+1:03d}',l,continuation='ATC' if arm=='BC_PPO_OFF' and teacher=='LEX_ATC' else 'EDF')",`                for ep in range(32):
                    row=simulate(training[ep%8],arm,'TRAIN',arm+f'_TRAIN_{ep+1:03d}',l,continuation='EDF')
                    if ep<2:
                        parent=read(op['paired_prefix_expected'][str(ep+1)]['path'])['result'];actual=read(out/(row['label']+'.raw.json.gz'))['result']
                        for key in ('requests','trace','decisions'):assert B.G.canonical(parent[key])==B.G.canonical(actual[key]),'Exact sampled trajectory before first reward-dependent update'
                        del parent,actual;gc.collect()
                        if ep==1:B.G.write_new(out/'PAIRED_PREFIX_PASS.json',dict(status='PASS',episodes=[1,2],same_initial_actor_critic_Adam_action_shuffle_RNG=True,new_environment_START=0))`);
replace("evaluators={**arms,'CONTEXT_BC_ONLY':bc_only}","evaluators=arms");
replace("                for kind in op['public_policies']:simulate(case,kind,'RULE_EVAL',case['id']+'_'+kind,selector_kind='WEIGHTED',continuation='EDF')\n",'');
replace('            assert count==131','            assert count==63');
replace('new_training=32,new_updates=16,new_references=8,new_public_evaluations=30,new_evaluations=60,BC_epochs=64','new_training=32,new_updates=16,new_references=0,new_public_evaluations=0,new_evaluations=30,BC_epochs=0,reused_BC_epochs=64');
fs.writeFileSync(path.join(d,'run.py'),run,{flag:'wx'});
let audit=fs.readFileSync(path.join(parent,'audit.cjs'),'utf8');audit=audit.replace("res.new_START===131,'Predeclared finite context-only study'","res.new_START===63,'Predeclared finite joint-objective study'").replace("read(path.join(out,'STOCHASTIC_REPLAY.json')).BC_exact_optimizer_replay&&read(path.join(out,'STOCHASTIC_REPLAY.json')).exact_saved_greedy_replay","read(path.join(out,'STOCHASTIC_REPLAY.json')).reused_frozen_BC_warm&&read(path.join(out,'STOCHASTIC_REPLAY.json')).exact_saved_greedy_replay").replace("if(row.kind!=='P0'){","{");
const at=audit.indexOf(' const summary=[];'),until=audit.indexOf(' for(const arm of op.arms)',at);if(at<0||until<0)throw Error('Joint reward auditor block');
const reward=` const summary=[];
 need(read(path.join(out,'PAIRED_PREFIX_PASS.json')).status==='PASS','Original sampled prefix matched before reward-dependent update');
 for(const ep of [1,2]){const pin=op.paired_prefix_expected[String(ep)],row=res.rows.find(r=>r.kind==='TRAIN'&&r.label.endsWith('_'+String(ep).padStart(3,'0')));need(sha(pin.path)===pin.sha256,'Paired prefix parent SHA');const a=JSON.parse(zlib.gunzipSync(fs.readFileSync(pin.path))).result,b=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,row.label+'.raw.json.gz')))).result;for(const key of ['requests','trace','decisions'])need(JSON.stringify(a[key])===JSON.stringify(b[key]),'Independent exact sampled prefix physical history');}
 for(const row of res.rows){
  const r=records.find(x=>x.label===row.label),ref=op.reward_references[row.case],H0=row.reference_end_ns,D=(H0-35e9)/1e9,Q0=(ref.mean_AP_c-c.idle_c)*D;
  need(ref.common_increment_J_proxy>0&&Q0>0,'Positive fixed EDF normalizers');
  const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,row.label+'.raw.json.gz')))).result,trace=raw.trace,finish=r.completion?r.completion.end_ns:Math.round(design.find(s=>s.id===row.case).drain_stop_s*1e9),E=[0],Q=[0];
  for(const t of trace){const v=W.partial(t,t.dt,c,H);E.push(E.at(-1)+v.increment);Q.push(Q.at(-1)+v.temperature_area-c.idle_c*t.dt);}
  function prefix(time){if(time<=35e9)return [0,0];if(time>=trace.at(-1).end_ns)return [E.at(-1),Q.at(-1)];let lo=0,hi=trace.length;while(lo<hi){const m=(lo+hi)>>1;if(trace[m].start_ns<=time)lo=m+1;else hi=m;}const k=lo-1,dt=(time-trace[k].start_ns)/1e9,v=W.partial(trace[k],dt,c,H);return [E[k]+v.increment,Q[k]+v.temperature_area-c.idle_c*dt];}
  let previous=0,sum0=0;const calls=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,row.label+'.raw.json.gz')))).calls.filter(a=>!a.common_coalescing),saved=row.reward_audit.prefix_records;need(saved.length===calls.length,'All joint potential boundaries');
  for(let i=0;i<saved.length;i++){const end=i+1<calls.length?calls[i+1].time_ns:Math.max(finish,H0),e=prefix(Math.min(end,H0))[0],q0=Math.max(0,prefix(Math.min(end,H0))[1]),g=Math.max(e/ref.common_increment_J_proxy,q0/Q0),r0=saved[i];need(r0.end_ns===end,'Causal joint reward boundary');close(r0.common_increment_prefix_J_proxy,e,'Joint prefix energy',2e-6);close(r0.heat_excess_prefix_Cs,q0,'Joint prefix heat above idle',2e-6);close(r0.normalized_worst,g,'Independent max scalarization',2e-7);close(r0.cost0,2*(g-previous),'Independent potential difference',2e-7);sum0+=r0.cost0;previous=g;}
  close(row.reward_audit.cost_sum[0],sum0,'Joint reward telescope');close(row.reward_audit.cost_sum[1],0,'No compensating heat objective',0);
  const expected=r.original.cost_vector.slice(2);expected[2]+=raw.requests.filter(q=>q.available_ns===null||q.available_ns>H0).length/row.n;for(let k=0;k<3;k++)close(row.reward_audit.cost_sum[k+2],expected[k],'Unchanged soft deadline objectives',2e-6);
 }
`;
audit=audit.slice(0,at)+reward+audit.slice(until);fs.writeFileSync(path.join(d,'audit.cjs'),audit,{flag:'wx'});
let pre=fs.readFileSync(path.join(parent,'preflight.py'),'utf8');pre=pre.replace("'queue_context_tests'","'minmax_joint_tests'");pre=pre.replace("    assert producer.HERE==HERE and producer.PublicController.__module__=='queue_controller'","    assert producer.HERE==HERE and producer.PublicController.__module__=='queue_controller'\n    warm=producer.loadpt(ROOT/'results/QUEUE_CONTEXT_20261018_01/CONTEXT_BC_ONLY.FINAL_WARM.pt.gz')\n    initial=producer.Learner(warm,anchor=True)\n    producer.equal(initial.snapshot(),producer.loadpt(ROOT/'results/QUEUE_CONTEXT_20261018_01/CONTEXT_BC_PPO_OFF_TRAIN_001.BEFORE.pt.gz'))").replace("actual_producer_import='PASS',new_environment_START=0","actual_producer_import='PASS',paired_initial_actor_critic_Adam_RNG_exact=True,new_environment_START=0").replace('Queue context preflight failed','Joint objective preflight failed');fs.writeFileSync(path.join(d,'preflight.py'),pre,{flag:'wx'});
console.log('MINMAX_SOURCES_BUILT');
