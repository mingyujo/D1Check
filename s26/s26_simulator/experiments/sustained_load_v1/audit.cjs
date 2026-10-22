'use strict';
const assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const C=require('./common.cjs'),{fs,path}=C,op=C.read(path.join(C.HERE,'OPERATION.json'));C.verify(op);
const terminal=C.read(path.join(op.output,'TERMINAL.json')),rows=fs.existsSync(path.join(op.output,'rows.jsonl'))?fs.readFileSync(path.join(op.output,'rows.jsonl'),'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse):[];
let checks=0,publicDigests=0,maxWorkError=0;
for(const row of rows){assert.equal(C.sha(fs.readFileSync(row.raw_path)),row.raw_sha256);checks++;
 const {simulation:r,spec}=C.read(row.raw_path);assert.equal(r.planned_requests.length,spec.n);checks++;
 const requests=new Map(r.requests.map(q=>[q.ordinal,q]));assert.equal(requests.size,r.requests.length);assert.equal(r.requests.length+r.unfinished,spec.n);checks+=2;
 for(const q of r.requests){assert.ok(q.times.dispatch>=q.arrival-1e-9);assert.ok(q.response<=q.times.AVAILABLE+1e-9);assert.ok(q.times.AVAILABLE<=spec.config.horizon_s+1e-8);checks+=3;}
 for(const slot of ['CPU','GPU','NPU']){const jobs=r.requests.filter(q=>(q.route.endsWith('_GPU')?'GPU':q.route.endsWith('_NPU')?'NPU':'CPU')===slot).sort((a,b)=>a.times.dispatch-b.times.dispatch);for(let i=1;i<jobs.length;i++){assert.ok(jobs[i-1].times.AVAILABLE<=jobs[i].times.dispatch+1e-8);checks++;}}
 const cpu=r.cpu_intervals.slice().sort((a,b)=>a.start-b.start);for(let i=1;i<cpu.length;i++){assert.ok(cpu[i-1].end<=cpu[i].start+1e-8);checks++;}
 const progress=new Map;for(const [time,dt,entries] of r.advances)for(const [ordinal,before,rate] of entries){const previous=progress.get(ordinal)??0;assert.ok(Math.abs(before-previous)<1e-7);progress.set(ordinal,previous+dt*rate);checks++;}
 for(const q of r.requests){const error=Math.abs((progress.get(q.ordinal)??0)-1);maxWorkError=Math.max(maxWorkError,error);assert.ok(error<1e-7);checks++;}
 for(const d of r.policy_decisions){const obs=d.public_observation;assert.equal(obs.cost_state.activity9.encoding,'FINAL_ACTIVITY_PREFIX');
  const intervals=r.activity.map(xs=>xs.filter(x=>x[0]<d.time).map(([l,end,w])=>[l,Math.min(end,d.time),w]));
  const restored={...obs,cost_state:{...obs.cost_state,activity9:{intervals}}};
  assert.equal(C.sha(Buffer.from(JSON.stringify(restored))),d.action.public_digest);publicDigests++;checks++;
  for(const q of obs.ready){assert.ok(q.arrival<=d.time+1e-9);checks++;}
  for(const owner of obs.owners)for(const t of Object.values(owner.times)){assert.ok(t===null||t<=d.time+1e-9);checks++;}
 }
}
assert.equal(terminal.complete,rows.length);assert.equal(terminal.started,terminal.complete+terminal.fail);checks+=2;
const py=spawnSync(path.join('C:/Users/user/anaconda3/python.exe'),[path.join(C.HERE,'audit_energy.py')],{cwd:C.HERE,encoding:'utf8',maxBuffer:2*1024**2});
if(py.status!==0)throw Error('Independent Python cost audit: '+py.stderr);console.log(py.stdout.trim());
const independent=C.read(path.join(op.output,'INDEPENDENT_ENERGY_AUDIT.json'));
C.write(path.join(op.output,'AUDIT.json'),{status:'PASS_FOR_SAVED_COMPLETES',checks,publicDigests,maxWorkError,independent,completed:rows.length,failed:terminal.fail,physical_prediction_validity:false,new_policy_environments:0,new_fit:0,new_RL:0});
console.log(JSON.stringify({status:'PASS_FOR_SAVED_COMPLETES',checks,publicDigests,maxWorkError,completed:rows.length,failed:terminal.fail}));
