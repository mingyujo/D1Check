'use strict';
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const {Engine}=require('./engine.cjs'),m=require('./method.cjs'),{legal}=require('./contract.cjs');
const {a24Profile,s26Profile,matchedResourceScenario}=require('./profiles.cjs');
const ev=require('./evaluation.cjs');
const workload=require('./workload.cjs');
let tests=0;function check(name,f){try{f();tests++;console.log('PASS',name);}catch(e){console.error('FAIL',name);throw e;}}
class ToyPhysics{
 constructor(){this.time=0;this.J=0;this.H=0;this.T=26;this.ambient_c=26;}
 clone(){return Object.assign(new ToyPhysics,this);}exportState(){return {...this};}temperature(){return this.T;}power(){return 1;}
 advance(dt,owners){this.J+=dt*(1+owners.length);this.H+=26*dt;this.time+=dt;}
}
function toy(options={}){const p={id:'TOY',allowed:{C:['CPU','GPU','NPU'],D:['CPU']},owner_capacity:{CPU:1,GPU:1,NPU:1},cpu_service_workers:1,energy_scale:1,baselinePower:1,resource_evidence:'SYNTHETIC',response_contract:{C:'output',D:'readback'},createPhysics:()=>new ToyPhysics,fromPublic:s=>Object.assign(new ToyPhysics,s),nominalPhases:(q,r)=>[{name:'INFER',work:.1,cpu_service:r==='CPU'},{name:'POST',work:.1,cpu_work:.05,response_at:q.task==='C'?0:.03}],actualPhases:(q,r)=>p.nominalPhases(q,r),rate:()=>1,publicRate:()=>1,advance:(phys,owners,cpus,dt)=>phys.advance(dt,owners),...options};return p;}
const q=(id='q0',task='C',priority='U',ready=0,due=1)=>({id,ordinal:+id.replace(/\D/g,'')||0,task,priority,arrival_s:ready,ready_s:ready,deadline_s:due,source_kind:'SYNTHETIC'});
const initial=(p,queue=[q()])=>new Engine(p,queue,p.createPhysics(),{start_s:0,end_s:2,mode:'CONFORMANCE'}).snapshot();
const snapshot=(p,queue=[q()])=>{const e=new Engine(p,queue,p.createPhysics(),{start_s:0,end_s:2,mode:'CONFORMANCE'});e.admit();return e.snapshot();};
check('same engine returns semantic response before AVAILABLE',()=>{const p=toy(),e=new Engine(p,[q()],p.createPhysics(),{start_s:0,end_s:1}).run(m.baseline(p,'FIFO'));assert.equal(e.done.length,1);assert.ok(Math.abs(e.done[0].response_s-.1)<1e-9);assert.ok(Math.abs(e.done[0].available_s-.2)<1e-9);});
check('task response boundary independent of priority',()=>{for(const priority of ['U','N']){const p=toy(),e=new Engine(p,[q('q1','D',priority)],p.createPhysics(),{start_s:0,end_s:1}).run(m.baseline(p,'FIFO'));assert.ok(Math.abs(e.done[0].response_s-.13)<1e-9);}});
check('CPU3 service does not create CPU3 backend owners',()=>{const p=toy({cpu_service_workers:3});assert.equal(legal(p,q(),'CPU',[{route:'CPU'}]),false);assert.equal(legal(p,q(),'GPU',[{route:'CPU'}]),true);});
check('backend ownership held through post phase',()=>{const p=toy({allowed:{C:['CPU'],D:['CPU']}}),e=new Engine(p,[q('q1'),q('q2')],p.createPhysics(),{start_s:0,end_s:1}).run(m.baseline(p,'FIFO'));assert.ok(e.done[1].dispatch_s>=e.done[0].available_s-1e-9);});
check('shared host CPU service queues across routes',()=>{const p=toy(),e=new Engine(p,[q('q1'),q('q2')],p.createPhysics(),{start_s:0,end_s:1}).run(s=>{const v=s.queue[0];return {kind:'DISPATCH',id:v.id,route:v.id==='q1'?'GPU':'NPU'};});for(const t of e.trace)assert.ok(t.cpu_services.length<=1);assert.ok(e.done.some(o=>o.available_s>.2+1e-9));});
check('FIFO is real ready entry order',()=>{const p=toy(),s=snapshot(p,[q('q1'),q('q2')]);s.queue[0].arrival_s=-2;s.queue[0].ready_s=-.1;s.queue[1].arrival_s=-1;s.queue[1].ready_s=-.2;assert.equal(m.baseline(p,'FIFO')(s).id,'q2');});
check('future arrivals and private work absent from public snapshot',()=>{const p=toy(),e=new Engine(p,[{...q(),private_work:{CPU:[.7]}},q('q2','C','U',10)],p.createPhysics(),{start_s:0,end_s:1});e.admit();const s=e.snapshot();assert.equal(s.queue.length,1);assert.ok(!JSON.stringify(s).includes('private_work'));});
check('nominal forecast never calls latent actual work',()=>{const p=toy({actualPhases:()=>{throw Error('Latent access');}}),s=snapshot(p);const bank=m.encode(p,s);assert.ok(bank&&bank.actions.length);assert.equal(bank.x[0].length,50);});
check('future injected into forecast is rejected',()=>{const p=toy(),s=snapshot(p);assert.throws(()=>m.forecast(p,s,{kind:'WAIT',wait_s:.02},[{...q(),ready_s:10}],1),/Future/);});
check('common horizon reduces every candidate consistently',()=>{const p=toy(),s=snapshot(p),ctx=m.candidates(p,s),fs=m.predictActions(p,s,ctx,{max_steps:5});assert.ok(fs.every(f=>f.capped&&f.comparison_complete));assert.ok(fs.every(f=>Math.abs(f.H_s-fs[0].H_s)<1e-9));});
check('WAIT_EVENT wakes at new public arrival',()=>{const p=toy(),e=new Engine(p,[q('q1'),q('q2'),q('q3','C','U',.03)],p.createPhysics(),{start_s:0,end_s:.5});let once=false;e.run(s=>{const id=s.queue[0].id;if(id==='q1')return {kind:'DISPATCH',id,route:'CPU'};if(!once){once=true;return {kind:'WAIT_EVENT'};}return {kind:'DISPATCH',id,route:id==='q2'?'GPU':'NPU'};});assert.ok(Math.abs(e.events.find(e=>e.kind==='DISPATCH'&&e.id==='q2').time_s-.03)<1e-9);});
check('idle filter removes only proven dominated wait',()=>{const s={owners:[],queue:[q()]},as=[{kind:'DISPATCH',id:'q0',route:'CPU'},{kind:'WAIT',wait_s:.02}],base={AP_end:26,peak:26,H_s:1,comparison_complete:true,capped:false,visible_ids:['q0']};const f=m.idleFilter(s,as,[{...base,cost:[1,0,0,0,0]},{...base,cost:[2,0,0,0,0]}],[true,true]);assert.deepEqual(f.mask,[true,false]);assert.deepEqual(m.idleFilter({...s,owners:[{}]},as,[],[true,true]).mask,[true,true]);});
check('compatible labels include task priority deadline and route',()=>{const p=toy(),s=snapshot(p,[q('q1'),q('q2')]),b=m.encode(p,s),i=m.teacher(b),mask=m.compatibleTargets(s,b,i);assert.ok(mask[i]);assert.equal(mask.length,27);});
check('profiles with identical parameters cannot use a device-name policy branch',()=>{const p=toy({id:'A24'}),r=toy({id:'S26'}),s=snapshot(p,[q('q1'),q('q2','D','N')]),a=m.encode(p,s),b=m.encode(r,s);assert.deepEqual(a,b);});
check('measured episode cannot use conformance mode',()=>{const p=toy();assert.throws(()=>new Engine(p,[{...q(),source_kind:'MEASURED'}],p.createPhysics(),{start_s:0,end_s:1}),/registered/);assert.throws(()=>new Engine(p,[q()],p.createPhysics(),{mode:'REGISTERED',start_s:0,end_s:1}),/START/);});
check('route support and no drop are common hard constraints',()=>{const p=toy(),e=new Engine(p,[q('q1','D')],p.createPhysics(),{start_s:0,end_s:1});e.admit();assert.throws(()=>e.dispatch({id:'q1',route:'NPU'}),/Illegal/);assert.throws(()=>e.apply({kind:'DROP',id:'q1'}),/Unknown/);});
check('invalid legacy owner snapshot rejected before encoding',()=>{const p=toy(),s=snapshot(p);s.owners=[{...q('q1'),route:'CPU',stage:0,phase_progress_public:0},{...q('q2'),route:'CPU',stage:0,phase_progress_public:0}];assert.throws(()=>m.encode(p,s),/resource scenario/);});
check('all arrivals including missing/drop remain service denominator',()=>{const s=ev.service([{...q('q1'),response_s:.1,available_s:.2},{...q('q2'),response_s:null,available_s:null,dropped:true}],1);assert.equal(s.ALL.arrived,2);assert.equal(s.ALL.responded,1);assert.equal(s.ALL.on_time,1);assert.equal(s.ALL.dropped,1);});
check('symmetric window extends for the slowest policy',()=>{assert.equal(ev.commonEnd([{requests:[{available_s:7}]},{requests:[{available_s:9}]}],5,20),9);assert.equal(ev.commonEnd([{requests:[{available_s:null}]}],5,20),20);});
check('cross device energy units cannot be silently combined',()=>assert.throws(()=>ev.compareUnits({energy_unit:'API_J',J:1},{energy_unit:'J_PROXY',J:1}),/interchangeable/));
check('NOMINAL mode cannot bypass registered private workload',()=>{const p=toy();assert.throws(()=>new Engine(p,[q()],p.createPhysics(),{mode:'NOMINAL'}),/private actual work/);});
check('physical and event clocks cannot have different origins',()=>{const p=toy();assert.throws(()=>new Engine(p,[q()],p.createPhysics(),{start_s:35,end_s:36}),/same start/);});
check('unknown baseline name cannot silently become FIFO',()=>assert.throws(()=>m.baseline(toy(),'TYPO'),/Explicit/));
const data=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../a24_simulator/experiments/a24_s26_common_20261020/PROFILES.json'),'utf8'));
check('native parameter fixtures load for both devices',()=>{for(const p of [a24Profile(data.A24),s26Profile(data.S26)])assert.ok(Number.isFinite(p.createPhysics().temperature()));});
check('matched resources share backend1 and CPU service3 semantics',()=>{for(const p of [a24Profile(data.A24),s26Profile(data.S26)].map(matchedResourceScenario)){assert.equal(p.owner_capacity.CPU,1);assert.equal(p.cpu_service_workers,3);assert.equal(legal(p,q(),'CPU',[{route:'CPU'}]),false);}});
check('real profiles share feature ABI in public nominal evaluation',()=>{for(const p of [a24Profile(data.A24),s26Profile(data.S26)].map(matchedResourceScenario)){const phys=p.createPhysics(),s={time_s:35,queue:[{...q(),arrival_s:35,ready_s:35,deadline_s:36}],owners:[],sensor:{temperature_c:phys.temperature(),ambient_c:phys.ambient_c,power:phys.power(),cost_state:phys.exportState()},wait_used_s:0,dispatch_stop_s:50},bank=m.encode(p,s);assert.ok(bank.mask[m.teacher(bank)]);assert.equal(bank.x.length,27);assert.equal(bank.x[0].length,50);}});
check('both physical profiles execute synthetic requests in the same engine',()=>{
 for(const p of [a24Profile(data.A24),s26Profile(data.S26)].map(matchedResourceScenario)){
  const qs=[q('q1'),q('q2','D','N')].map(x=>({...x,arrival_s:35,ready_s:35,deadline_s:39}));
  for(const x of qs){x.private_work={};x.private_phases={};for(const r of p.allowed[x.task]){x.private_work[r]=data.A24.nominal[x.task+'_'+r];x.private_phases[r]=p.nominalPhases(x,r,p.createPhysics().temperature());}}
  const phys=p.createPhysics(),startJ=phys.J,e=new Engine(p,qs,phys,{start_s:35,end_s:40,mode:'CONFORMANCE'}).run(m.baseline(p,'FIFO'));
  assert.equal(e.done.length,2);assert.ok(e.done.every(q=>q.response_s<=q.available_s));const full=ev.integrate(e.trace,p,35,40),part=ev.integrate(e.trace,p,35.017,39.991);
  assert.ok(Math.abs(full.J-(e.physics.J-startJ))<1e-8);assert.ok(part.J>0&&part.J<full.J);
 }
});
const spec={n:32,offered_requests_per_s:2,classification_share:.5,urgent_share:.25,deadlines_s:{C:{U:.8,N:2},D:{U:1,N:3}},seed:20261020};
check('same workload spec gives identical arrivals for either device',()=>assert.deepEqual(workload.plan(spec),workload.plan({...spec})));
check('priority is independent of task in the common generator',()=>{const w=workload.plan({...spec,n:1000,urgent_share:.5});assert.deepEqual(new Set(w.requests.map(q=>q.task+q.priority)),new Set(['CU','CN','DU','DN']));});
check('admission jitter cannot alter original response deadline',()=>{const w=workload.plan(spec),a=Object.fromEntries(w.requests.map(q=>[q.id,.1])),qs=workload.bindAdmission(w,a,{source_kind:'SYNTHETIC'});assert.ok(qs.every((q,i)=>q.deadline_s===w.requests[i].deadline_s&&Math.abs(q.ready_s-q.arrival_s-.1)<1e-9));});
check('admission is explicit rather than silently zero',()=>assert.throws(()=>workload.bindAdmission(workload.plan(spec),{}),/admission/));
check('invalid common response budget is rejected',()=>assert.throws(()=>workload.plan({...spec,deadlines_s:{}}),/budgets/));
check('input generation has no device identity parameter',()=>{const a=workload.plan({...spec,device:'A24'}),b=workload.plan({...spec,device:'S26'});assert.deepEqual(a,b);});
console.log(JSON.stringify({status:'PASS',tests,new_environment:0,new_measurements:0,synthetic_only_engine_tests:true,real_profile_nominal_only:true}));
