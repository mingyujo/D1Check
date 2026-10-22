'use strict';
const fs=require('fs'),path=require('path'),d=__dirname,prior=path.resolve(d,'../packing_rl_20261018');let s=fs.readFileSync(path.join(prior,'run_packing.py'),'utf8');
const change=(a,b)=>{if(!s.includes(a))throw Error('Expected parent producer '+a.slice(0,100));s=s.replace(a,b);};
change("sys.path.insert(0,str(HERE))\nfrom packing_encoder", "sys.path.insert(0,str(HERE.parent/'packing_rl_20261018'))\nsys.path.insert(0,str(HERE))\nfrom packing_encoder");change('from completion_labels import labels','from event_labels import labels');change("('packing_rl_20261018',)","('deadline_event_20261018',)");
const replayStart=s.indexOf('def replay('),replayEnd=s.indexOf('def main():',replayStart);if(replayStart<0||replayEnd<0)throw Error('Parent replay block');
s=s.slice(0,replayStart)+`def replay(out,rows):
    episodes=frames=updates=greedy=0
    for row in rows:
        source=out/(row['label']+'.BEFORE.pt.gz') if row['kind']=='TRAIN' else out/row['network_file'];learner=Learner(loadpt(source));data=loadpt(out/(row['label']+'.frames.pt.gz'))
        for f in data['frames']:
            i,again=learner.choose({k:f[k] for k in ('x','mask','scores')},row['kind']=='TRAIN');assert i==f['index'] and again['old_logp']==f['old_logp'] and np.array_equal(again['value'],f['value']);frames+=1
        if row['kind']=='TRAIN':
            before=learner.updates;learner.add(data['frames'],data['costs']);equal(learner.snapshot(),loadpt(out/(row['label']+'.AFTER.pt.gz')));updates+=learner.updates-before;episodes+=1
        else:greedy+=len(data['frames'])
    B.G.write_new(out/'STOCHASTIC_REPLAY.json',dict(status='PASS',BC_exact_optimizer_replay=False,reused_frozen_BC_warm=True,BC_epochs=0,reused_BC_epochs=64,exact_saved_greedy_replay=True,episodes=episodes,frames=frames,greedy_frames=greedy,exact_saved_optimizer_update_replays=updates,new_environment_START=0,new_training_data=0))

`+s.slice(replayEnd);
change("joint=not policy.startswith('PACKING_ENERGY')","joint=not policy.startswith('EVENT_ENERGY')");
const a=s.indexOf('            env=envelopes('),b=s.indexOf("            for arm in op['arms']:",a);if(a<0||b<0)throw Error('Teacher/BC replacement site');
s=s.slice(0,a)+`            warm=loadpt(op['warm_checkpoint']['path']);equal(warm,loadpt(op['paired_initial_snapshot']['path']));pt(out/'REUSED_BC_WARM.pt.gz',warm)
            B.G.write_new(out/'WARM_EXACT.json',dict(status='PASS',full_actor_critic_two_Adam_and_RNG_exact=True,new_BC_epochs=0,reused_BC_epochs=64))
`+s.slice(b);
const at="                    if arm==op['arms'][1] and ep<2:";
change(at,`                    if ep<2:
                        expected=read(Path(op['parent_output'])/(op['parent_arm_map'][arm]+f'_TRAIN_{ep+1:03d}.raw.json.gz'))['result'];actual=read(out/(row['label']+'.raw.json.gz'))['result']
                        for key in ('requests','trace','decisions'):assert B.G.canonical(expected[key])==B.G.canonical(actual[key]),'Exact matched parent before first reward-dependent update'
                        del expected,actual;gc.collect()
                        if ep==1:B.G.write_new(out/(arm+'.PAIRED_PARENT_PREFIX_PASS.json'),dict(status='PASS',episodes=[1,2],parent_arm=op['parent_arm_map'][arm]))
`+at);
change("                simulate(case,'PACKING_PUBLIC','RULE_EVAL')\n                for arm in ['PACKING_BC_ONLY',*op['arms']]:", "                for arm in op['arms']:");
change('assert count==192 and solves==8','assert count==124 and solves==0');change('new_experts=8,new_evaluations=120,new_LP_solves=solves,BC_epochs=64','new_experts=0,new_evaluations=60,new_LP_solves=solves,BC_epochs=0,reused_BC_epochs=64');
fs.writeFileSync(path.join(d,'run_event.py'),s,{flag:'wx'});
let audit=fs.readFileSync(path.join(prior,'audit.cjs'),'utf8').replace("T=require('./tensor_reader.cjs'),F=require('./feature_audit.cjs')","T=require('../packing_rl_20261018/tensor_reader.cjs'),F=require('../packing_rl_20261018/feature_audit.cjs')").replace('res.new_START===192','res.new_START===124');
audit=audit.replace("read(path.join(out,'STOCHASTIC_REPLAY.json')).BC_exact_optimizer_replay&&", "read(path.join(out,'STOCHASTIC_REPLAY.json')).reused_frozen_BC_warm&&");
const reward="  close(audit.cost_sum[0],2*prior,'Final completion objective',2e-6);";if(!audit.includes(reward))throw Error('Deadline-prefix audit insertion');
audit=audit.replace(reward,`  need(audit.deadline_event_redistribution&&audit.deadline_event_records.length===calls.length,'Every event-timed deadline prefix');let before=[0,0];
  for(const record of audit.deadline_event_records){const expected=[0,0];for(const q of raw.requests){if(q.response_ns===null||q.response_ns>Math.round(design.find(x=>x.id===row.case).drain_stop_s*1e9))continue;const late=Math.max(0,Math.min(record.end_ns,q.response_ns)/1e9-q.deadline_ns/1e9),loss=Number(late>1e-9)+.2*Math.min(5,late/Math.max(.05,(q.deadline_ns-q.scheduled_arrival_ns)/1e9));expected[q.priority==='U'?0:1]+=loss/row.n;}for(let k=0;k<2;k++){close(record.prefix_cost[k],expected[k],'Independent deadline-crossing prefix',2e-7);close(record.increment[k],expected[k]-before[k],'Independent deadline event increment',2e-7);}before=expected;}
`+reward);
fs.writeFileSync(path.join(d,'audit.cjs'),audit,{flag:'wx'});fs.copyFileSync(path.join(prior,'THERMAL_PURE_TEST.json'),path.join(d,'THERMAL_PURE_TEST.json'),fs.constants.COPYFILE_EXCL);console.log('CONDITIONAL_DEADLINE_EVENT_SOURCES_BUILT');
