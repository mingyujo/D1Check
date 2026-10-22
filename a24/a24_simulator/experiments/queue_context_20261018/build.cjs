'use strict';
const fs=require('fs'),path=require('path'),d=__dirname,prior=path.resolve(d,'../deep_repair_20261018');
let run=fs.readFileSync(path.join(prior,'run.py'),'utf8');
function replace(from,to){if(!run.includes(from))throw Error('Expected original run source '+from.slice(0,100));run=run.replace(from,to);}
replace('from common import B,HERE,ROOT,np,torch,read,saved,pt,loadpt,Selector',"import sys\nsys.path.insert(0,str(Path(__file__).resolve().parent.parent/'deep_repair_20261018'))\nfrom common import B,ROOT,np,torch,read,saved,pt,loadpt,Selector\nHERE=Path(__file__).resolve().parent\nB.G.OWN_TOKENS+=('queue_context_20261018',)");
replace('from public_controller import PublicController','from queue_controller import QueueContextController as PublicController');
replace("    assert '--published' in __import__('sys').argv", "    assert '--published' in __import__('sys').argv\n    committed=subprocess.check_output(['git','show','HEAD:'+str((HERE/'OPERATION.json').relative_to(ROOT.parent)).replace('\\\\','/')])\n    assert __import__('hashlib').sha256(committed).hexdigest()==opsha,'Published context operation required'");
replace('            from diagnostics import run as probes\n            probes(out)',"            B.G.write_new(out/'GRADIENT_PROBES.json',read(ROOT/'results/DEEP_REPAIR_20261018_01/GRADIENT_PROBES.json'))");
replace("for kind in op['public_policies']:simulate(case,kind,'REFERENCE'","for kind in ['BANK_ATC']:simulate(case,kind,'REFERENCE'");
const start=run.indexOf('            ref={k:'),end=run.indexOf('            x=[];mask=[];',start);if(start<0||end<0)throw Error('Teacher selection section');
run=run.slice(0,start)+`            ref={'BANK_ATC':[r for r in rows if r['kind']=='REFERENCE']};teacher='BANK_ATC'
            for row in ref[teacher]:
                old=read(ROOT/'results/DEEP_REPAIR_20261018_01'/(row['label']+'.raw.json.gz'))['result'];new=read(out/(row['label']+'.raw.json.gz'))['result']
                for key in ('requests','trace','decisions'):assert B.G.canonical(old[key])==B.G.canonical(new[key]),'Same ATC reference schedule despite expanded forecasts'
                del old,new;gc.collect()
            B.G.write_new(out/'TEACHER_SELECTION.json',dict(teacher=teacher,training_only8=True,evaluation_used=False,fixed_public_teacher=True,all8_reference_schedules_exact_to_parent=True))
`+run.slice(end);
replace("calibrated=Learner(copy.deepcopy(initial));improved=Learner(copy.deepcopy(initial))","improved=Learner(copy.deepcopy(initial))");
replace("pt(out/'BC_DATA.pt.gz',dataset)","pt(out/'BC_DATA.pt.gz',dataset)\n            del raw,x,mask,target,source_labels;gc.collect()");
replace("arms=dict(CALIBRATED_PPO_OFF=calibrated,BC_PPO_OFF=improved)","arms=dict(CONTEXT_BC_PPO_OFF=improved)");
run=run.replaceAll("'BC_ONLY.FINAL_WARM.pt.gz'","'CONTEXT_BC_ONLY.FINAL_WARM.pt.gz'").replaceAll("policy=='BC_ONLY'","policy=='CONTEXT_BC_ONLY'");
replace("evaluators={**arms,'BC_ONLY':bc_only}","evaluators={**arms,'CONTEXT_BC_ONLY':bc_only}");
replace("for kind in op['public_policies']:simulate(case,kind,'RULE_EVAL',case['id']+'_'+kind,selector_kind=kind,continuation='ATC' if kind=='LEX_ATC' else 'EDF')","for kind in op['public_policies']:simulate(case,kind,'RULE_EVAL',case['id']+'_'+kind,selector_kind='WEIGHTED',continuation='EDF')");
replace("            assert count==308","            assert count==131");
const begin=run.indexOf('            maxima={p:'),finish=run.indexOf("            for pin in op['sources']",begin);if(begin<0||finish<0)throw Error('Conditional cap section');run=run.slice(0,begin)+run.slice(finish);
replace('new_training=64,new_updates=32,new_references=32,new_public_evaluations=120,new_evaluations=90','new_training=32,new_updates=16,new_references=8,new_public_evaluations=30,new_evaluations=60');
fs.writeFileSync(path.join(d,'run.py'),run,{flag:'wx'});
let audit=fs.readFileSync(path.join(prior,'audit.cjs'),'utf8');
audit=audit.replace("need(res.new_START===308||res.new_START===338,'Predeclared finite base or conditional count')","need(res.new_START===131,'Predeclared finite context-only study')").replace(".episodes===64&&read(path.join(out,'STOCHASTIC_REPLAY.json')).exact_saved_optimizer_update_replays===32",".episodes===32&&read(path.join(out,'STOCHASTIC_REPLAY.json')).exact_saved_optimizer_update_replays===16").replace('forecast.visible_jobs<=10','forecast.visible_jobs<=26');
audit=audit.replace("[x[i][27],x[i][25]+x[i][26],x[i][25],.5*x[i][23]+.5*x[i][24],i]","[x[i][27],Math.fround(x[i][25]+x[i][26]),x[i][25],Math.fround(Math.fround(.5*x[i][23])+Math.fround(.5*x[i][24])),i]");
const at="   const expected=call.time_ns/1e9+Math.max(.5,.5+bound/c.minimum_speed+.2);";
if(!audit.includes(at))throw Error('Forecast audit section');
audit=audit.replace(at,`   if(row.kind!=='P0'){
    need(call.forecast_context_cap===24&&call.action_candidates.length<=8,'Separate action and prediction capacities');
    const pending=q.filter(j=>j.queue_entry_ns<=call.time_ns&&(j.dispatch_ns===null||j.dispatch_ns>=call.time_ns)&&!call.nominal_owners.some(o=>o.request_id===j.request_id));
    const known=new Map(pending.map(j=>[j.request_id,j]));
    need(known.size===call.full_public_queue_size,'Only currently released and undispatched requests');
    const free=['CPU','GPU'].filter(r=>!call.nominal_owners.some(j=>j.route===r)),occ=(j,r)=>call.nominal_vectors[j.request_id+'|'+r].reduce((s,v)=>s+v,0)/Math.max(c.minimum_speed,1/(1+c.strength*(r==='CPU'?c.cpu_slope:c.gpu_slope)*Math.max(0,call.sensor.temperature_c-c.onset_c))),mean=pending.reduce((s,j)=>s+free.reduce((t,r)=>t+occ(j,r),0),0)/(pending.length*free.length),tie=(a,b)=>a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal||a.request_id.localeCompare(b.request_id),rank=j=>Math.max(...free.map(r=>Math.log((j.priority==='U'?2:1)/Math.max(.001,occ(j,r)))-Math.max(0,j.deadline_ns/1e9-call.time_ns/1e9-occ(j,r))/Math.max(.2,2*mean)));
    for(const j of pending)need(j.ordinal===jobmap.get(j.request_id).ordinal,'Frozen public ordinal');
    const edf=pending.slice().sort((a,b)=>a.deadline_ns-b.deadline_ns||tie(a,b)).slice(0,8),atc=pending.slice().sort((a,b)=>rank(b)-rank(a)||tie(a,b)).slice(0,8),expectedContext=new Set([...call.action_candidates,...edf,...atc].map(j=>j.request_id));
    for(const j of pending.slice().sort((a,b)=>a.deadline_ns-b.deadline_ns||tie(a,b))){if(expectedContext.size>=24)break;expectedContext.add(j.request_id);}
    need(expectedContext.size===call.nominal_ready.length&&call.nominal_ready.every(j=>known.has(j.request_id)&&expectedContext.has(j.request_id)),'Independent public context union');
   }
`+at);
// Request ordinals are checked against frozen bank public metadata.
fs.writeFileSync(path.join(d,'audit.cjs'),audit,{flag:'wx'});
console.log('CONTEXT_SOURCES_BUILT');
