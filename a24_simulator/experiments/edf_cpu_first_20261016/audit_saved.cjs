const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/EDF_CPU_FIRST_20261016_01');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0;const need=(v,m)=>{if(!v)throw Error(m);checks++},close=(a,b,m)=>need(Math.abs(a-b)<1e-7,m+': '+a+' / '+b);
const data=read(path.join(out,'RESULT.json')),old=read(path.join(root,'results/FOUR_ROUTE_V2_EVAL.json'));
need(read(path.join(out,'COMPLETE.json')).result_sha256===hash(path.join(out,'RESULT.json')),'Result pin');
need(!fs.existsSync(path.join(out,'FAILURE.json')),'No failed operation');
const manifest=read(path.join(root,'data/CORE_MANIFEST.json')),p=manifest.find(x=>x.name==='A24_measured35.json');
const profile=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(root,p.stored))));
const a=profile.cost_anchor.energy_increment_w,cc=a.classification_CPU,cg=a.classification_GPU,dc=a.detection_CPU,pair=a['classification_GPU+detection_CPU'];
const power={...a,detection_GPU:Math.max(0,dc+cg-cc),'classification_CPU+detection_GPU':pair,
 'classification_CPU+classification_GPU':Math.max(0,cc+pair-dc),'detection_CPU+detection_GPU':Math.max(0,dc+pair-cc)};
const interp=(t,y,x)=>{let i=0;while(i<t.length-2&&t[i+1]<x)i++;return y[i]+(y[i+1]-y[i])*(x-t[i])/(t[i+1]-t[i]);};
for(const c of data.cases){
 const oldRL=old.cases[c.index].rows.find(r=>r.policy==='ROLLING_ATC_RL');
 need(JSON.stringify(oldRL)===JSON.stringify(c.rows[0]),'Saved RL exact row '+c.index);
 const [lo,hi]=c.common_work_window_s;
 close(lo,Math.min(...c.input.requests.map(q=>q.arrival_s)),'Input start');
 close(hi,Math.min(180,Math.max(...c.input.requests.map(q=>q.arrival_s))+15),'Input end');
 c.rows.forEach((r,idx)=>{
  const m=c.metrics[idx],marks=[...new Set([lo,hi,...r.gantt.flatMap(x=>[Math.min(hi,Math.max(lo,x.start_s)),Math.min(hi,Math.max(lo,x.end_s))])])].sort((a,b)=>a-b);let inc=0;
  for(let i=1;i<marks.length;i++){
   const x=marks[i-1],y=marks[i],active=r.gantt.filter(q=>q.start_s<y&&q.end_s>x);
   need(active.length<=2&&new Set(active.map(q=>q.route)).size===active.length,'Physical owner occupancy');
   if(active.length){const key=active.map(q=>(q.task==='C'?'classification':'detection')+'_'+q.route).sort().join('+');need(key in power,'Known observer state');inc+=(y-x)*power[key];}
  }
  close(m.increment_J_proxy,inc,'Independent energy integral');
  close(m.baseline_J_proxy,profile.measured35.baseline_w*(hi-lo),'Independent baseline');
  close(m.total_J_proxy,m.baseline_J_proxy+inc,'Total decomposition');
  const t=r.AP.t_s,y=r.AP.ap_c,x=[lo,...t.filter(t=>t>lo&&t<hi),hi],v=x.map(x=>interp(t,y,x));let area=0;
  for(let i=1;i<x.length;i++)area+=(x[i]-x[i-1])*(v[i]+v[i-1])/2;
  close(m.mean_AP_c,area/(hi-lo),'Independent common-window heat');close(m.peak_AP_c,Math.max(...v),'Independent peak');
  need(m.on_time===r.requests.filter(q=>q.response_ns!==null&&q.response_ns<=q.deadline_ns).length,'Deadline denominator');
  need(m.AVAILABLE_by_window_end===r.requests.filter(q=>q.available_ns!==null&&q.available_ns<=hi*1e9+1e-5).length,'Window completion');
 });
 const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,'EDF_'+String(c.index).padStart(2,'0')+'.raw.json.gz'))));
 for(const d of raw.prediction.decisions){
  const s=d.public_state,q=s.queue.slice().sort((a,b)=>a.deadline_ns-b.deadline_ns||a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal||a.request_id.localeCompare(b.request_id))[0];
  need(d.action.kind==='DISPATCH'&&d.action.request_id===q.request_id,'Earliest deadline actual dispatch');
  const busy=new Set(s.owners.map(o=>o.route)),free=['CPU','GPU'].filter(x=>!busy.has(x));
  need(d.action.route===free[0],'CPU-first fixed resource tie actual dispatch');
 }
}
const receipts=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
for(const event of ['START','PREPARED','COMPLETE'])need(receipts.filter(r=>r.event===event).length===14,'Exact count '+event);
need(!receipts.some(r=>r.event==='FAIL'),'No consumed environment failures');
const r={status:'PASS_SAVED_14_EDF_14_RL_SAME_WINDOW',checks,RL_recomputed:0,new_environment:0,NN_training:0,
 result_sha256:hash(path.join(out,'RESULT.json')),source_sha256:hash(__filename),utc:new Date().toISOString()};
fs.writeFileSync(path.join(out,'INDEPENDENT_AUDIT.json'),JSON.stringify(r,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(r));
