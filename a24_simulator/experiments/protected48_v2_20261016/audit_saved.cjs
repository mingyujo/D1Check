// Independent saved-only arithmetic/resource/EDF/registration audit. No simulator.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/PROTECTED48_V2_20261016_01');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0;const need=(v,m)=>{if(!v)throw Error(m);checks++},close=(a,b,m,tol=1e-7)=>need(Math.abs(a-b)<tol,m+': '+a+' / '+b);
const d=read(path.join(out,'RESULT.json')),op=read(path.join(__dirname,'OPERATION.json'));
need(!fs.existsSync(path.join(out,'FAILURE.json')),'No operation failure');
need(read(path.join(out,'COMPLETE.json')).result_sha256===hash(path.join(out,'RESULT.json')),'Terminal result pin');
need(d.operation_sha256===hash(path.join(__dirname,'OPERATION.json')),'Operation pin');
for(const s of [...op.source_pins,...op.input_pins])need(hash(s.path)===s.sha256,'Input/source unchanged '+s.path);
const relocation=read(path.join(root,'data/PATH_MAP.json'));
for(const s of [...op.model_source_pins,...op.model_input_pins]){
 const item=relocation[s.path.replaceAll('\\','/').toLowerCase()];
 const p=item?path.join(root,'.cache',item.sha256):s.path;
 need(hash(p)===s.sha256,'Frozen physical source/input '+s.path);
}
const manifest=read(path.join(root,'data/CORE_MANIFEST.json')),spec=manifest.find(x=>x.name==='A24_measured35.json');
const profile=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(root,spec.stored))));
const a=profile.cost_anchor.energy_increment_w,cc=a.classification_CPU,cg=a.classification_GPU,dc=a.detection_CPU,pair=a['classification_GPU+detection_CPU'];
const power={...a,detection_GPU:Math.max(0,dc+cg-cc),'classification_CPU+detection_GPU':pair,'classification_CPU+classification_GPU':Math.max(0,cc+pair-dc),'detection_CPU+detection_GPU':Math.max(0,dc+pair-cc)};
function interp(t,y,x){let i=0;while(i<t.length-2&&t[i+1]<x)i++;return y[i]+(y[i+1]-y[i])*(x-t[i])/(t[i+1]-t[i]);}
function arithmetic(c){
 const [lo,hi]=c.common_work_window_s;
 close(lo,Math.min(...c.input.requests.map(q=>q.arrival_s)),'Input first arrival');
 close(hi,Math.min(180,Math.max(...c.input.requests.map(q=>q.arrival_s))+15),'Input last+15');
 for(let j=0;j<c.rows.length;j++){
  const r=c.rows[j],m=c.metrics[j],marks=[...new Set([lo,hi,...r.gantt.flatMap(x=>[Math.min(hi,Math.max(lo,x.start_s)),Math.min(hi,Math.max(lo,x.end_s))])])].sort((a,b)=>a-b);let inc=0;
  for(let i=1;i<marks.length;i++){
   const x=marks[i-1],y=marks[i],active=r.gantt.filter(q=>q.start_s<y&&q.end_s>x);
   need(active.length<=2&&new Set(active.map(q=>q.route)).size===active.length,'At most2 and one owner per resource');
   need(active.every(q=>['CPU','GPU'].includes(q.route)),'CPU/GPU only');
   if(active.length){const key=active.map(q=>(q.task==='C'?'classification':'detection')+'_'+q.route).sort().join('+');need(key in power,'Known observer state');inc+=(y-x)*power[key];}
  }
  close(m.increment_J_proxy,inc,'Work increment integral');close(m.baseline_J_proxy,profile.measured35.baseline_w*(hi-lo),'Same baseline');close(m.total_J_proxy,inc+m.baseline_J_proxy,'Total decomposition');
  const t=r.AP.t_s,y=r.AP.ap_c,x=[lo,...t.filter(t=>t>lo&&t<hi),hi],v=x.map(x=>interp(t,y,x));let area=0;
  for(let i=1;i<x.length;i++)area+=(x[i]-x[i-1])*(v[i]+v[i-1])/2;
  close(m.mean_AP_c,area/(hi-lo),'Time integral heat');close(m.peak_AP_c,Math.max(...v),'Window peak');close(m.end_AP_c,v.at(-1),'Window endpoint');
  need(m.on_time===r.requests.filter(q=>q.response_ns!==null&&q.response_ns<=q.deadline_ns).length,'All planned deadline denominator');
  need(m.response_missing===r.requests.filter(q=>q.response_ns===null).length,'Missing response');
  need(m.AVAILABLE_by_window_end===r.requests.filter(q=>q.available_ns!==null&&q.available_ns<=hi*1e9+1e-5).length,'Common-window resource release');
  const late=r.requests.reduce((s,q)=>s+(q.response_ns===null?0:Math.max(0,q.response_ns-q.deadline_ns)/1e9),0);
  close(m.total_tardiness_lower_bound_s,late,'Tardiness includes all completed');
 }
}
for(const group of ['fresh','historical','mechanism']){
 const cases=d[group+'_cases'];for(const c of cases)arithmetic(c);
 for(const ag of d.aggregate[group]){
  const rows=cases.map(c=>c.metrics.find(x=>x.policy===ag.policy));
  for(const k of ['total_J_proxy','increment_J_proxy','baseline_J_proxy','mean_AP_c','peak_AP_c','end_AP_c'])close(ag[k],rows.reduce((s,x)=>s+x[k],0)/rows.length,'Aggregate '+group+k);
  for(const k of ['planned','on_time','response_missing','AVAILABLE_by_window_end'])need(ag[k]===rows.reduce((s,x)=>s+x[k],0),'Aggregate denominator');
 }
}
need(d.training_episodes===64&&d.fresh_cases.length===24&&d.historical_cases.length===14&&d.mechanism_cases.length===12,'Registered counts');
const selection=read(path.join(out,'SELECTION_FROZEN.json'));
need(selection.evaluation_outcomes_opened===0,'DEV-only selection');
const ranked=selection.rankings.slice().sort((a,b)=>{for(let i=0;i<a.score.length;i++){if(a.score[i]!==b.score[i])return a.score[i]-b.score[i];}return a.episode-b.episode;});
need(ranked[0].episode===d.selected.episode,'Predeclared lexicographic selected');
need(hash(d.selected.checkpoint.path)===d.selected.checkpoint.sha256,'Selected checkpoint exact bytes');
const labels=fs.readdirSync(out).filter(n=>n.endsWith('.raw.json.gz'));
for(const n of labels){
 const r=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(out,n)))),p=r.prediction;
 for(const q of p.requests){
  if(q.response_ns===null)continue;
  need(q.scheduled_arrival_ns<=q.actual_arrival_ns&&q.actual_arrival_ns<=q.queue_entry_ns&&q.queue_entry_ns<=q.dispatch_ns&&q.dispatch_ns<=q.response_ns&&q.response_ns<=q.available_ns,'Request clocks');
 }
 if(r.summary.policy==='EDF_CPU_FIRST')for(const dec of p.decisions){
  const s=dec.public_state,q=s.queue.slice().sort((a,b)=>a.deadline_ns-b.deadline_ns||a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal||a.request_id.localeCompare(b.request_id))[0];
  need(dec.action.kind==='DISPATCH'&&dec.action.request_id===q.request_id,'Exact pure EDF order');
  const busy=new Set(s.owners.map(o=>o.route));need(dec.action.route===['CPU','GPU'].find(x=>!busy.has(x)),'EDF CPU-first free resource');
 }
 if(r.summary.protection_decisions)for(const b of r.summary.protection_decisions){need(b.mask[b.chosen_index]===true,'Chosen action protected mask');need(b.protection.uses_latent_duration_or_future_arrival===false,'Public-state protection contract');}
}
const receipts=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
for(const ev of ['START','PREPARED','COMPLETE'])need(receipts.filter(x=>x.event===ev).length===194,'Exact194 '+ev);
need(!receipts.some(x=>x.event==='FAIL'),'V2 failure0');
need(new Set(receipts.filter(x=>x.event==='START').map(x=>x.identity)).size===194,'Unique identities');
for(const e of receipts.filter(x=>x.event==='COMPLETE'))need(hash(path.join(out,e.label+'.raw.json.gz'))===e.raw_sha256,'Raw terminal SHA');
for(const c of d.fresh_cases){
 const n=c.metrics.find(x=>x.policy==='ROLLING_ATC_RL_PROTECTED48'),e=c.metrics.find(x=>x.policy==='EDF_CPU_FIRST'),t=d.targets.find(x=>x.case_index===c.index);
 const service=n.on_time>=e.on_time&&n.response_missing===0&&n.AVAILABLE_by_window_end===n.planned;
 need(t.no_service_harm===service,'No service harm target');need(t.target_total_10pct_AP_0_5===(service&&n.total_J_proxy<=.9*e.total_J_proxy&&n.mean_AP_c<=e.mean_AP_c-.5),'Original10%/0.5C target');
}
need(d.budget.current_shared_START===502&&d.budget.remaining===10,'Shared cap including predecessor failed2');
const result={status:'PASS_SAVED_ARITHMETIC_EDF_SOURCES_TARGETS_AND_194_RECEIPTS',checks,source_sha256:hash(__filename),result_sha256:hash(path.join(out,'RESULT.json')),new_environment:0,NN_update:0,physical_goal_validated:false,measured_J:null,utc:new Date().toISOString()};
fs.writeFileSync(path.join(out,'INDEPENDENT_AUDIT.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(result));
