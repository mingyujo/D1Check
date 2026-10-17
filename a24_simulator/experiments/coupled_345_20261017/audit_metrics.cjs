'use strict';
// Independent saved-request denominators, common-window costs, and objective.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),result=read(path.join(out,'RESULT.json'));
const source=read(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'));
const pw=Object.fromEntries(source.supported_states.map((s,i)=>[s,source.coefficients_W_proxy[i]])),H=pw.classification_GPU+pw.detection_CPU-pw['classification_GPU+detection_CPU'];
const inputs=read(op.inputs.path),cases=new Map(['train','dev','fresh'].flatMap(k=>inputs[k].map(c=>[c.id,c])));
let checks=0,maxError=0;const flags=[];
function need(v,s){checks++;if(!v)throw Error(s);}
function close(a,b,s,tol=1e-6){maxError=Math.max(maxError,Math.abs(a-b));need(Math.abs(a-b)<tol,s);}
for(const row of result.rows){
 const file=path.join(out,row.label+'.raw.json.gz');need(sha(file)===row.raw_sha256,'Raw SHA');
 const raw=JSON.parse(z.gunzipSync(fs.readFileSync(file))),r=raw.result,c=cases.get(row.case),q=r.requests,conf=r.config,m=row.metrics;
 need(q.length===c.n&&new Set(q.map(x=>x.request_id)).size===c.n,'All planned identities retained');
 const answered=q.filter(x=>x.response_ns!=null&&x.response_ns/1e9<=c.drain_stop_s),due=x=>x.response_ns<=x.deadline_ns;
 need(answered.length===m.responded&&c.n-answered.length===m.response_missing,'No missing completion removed');
 need(answered.filter(due).length===m.on_time&&answered.filter(x=>x.priority==='U'&&due(x)).length===m.urgent_on_time,'All deadline outcomes');
 need(q.filter(x=>x.priority==='U').length===m.urgent_planned,'Urgent planned denominator');
 need(q.filter(x=>x.available_ns==null||x.available_ns/1e9>c.drain_stop_s).length===m.incomplete,'AVAILABLE incomplete retained');
 const latency=answered.map(x=>(x.response_ns-x.scheduled_arrival_ns)/1e9).sort((a,b)=>a-b);
 if(latency.length)close(latency[Math.ceil(.95*latency.length)-1],m.P95_completed_response_s,'Conditional P95');else need(m.P95_completed_response_s===null,'No invented latency');
 const traces=r.trace.filter(t=>t.start_ns/1e9>=35-1e-9&&t.end_ns/1e9<=c.drain_stop_s+1e-9),work=r.trace.filter(t=>t.start_ns/1e9>=35-1e-9&&t.end_ns/1e9<=c.service_stop_s+1e-9);
 const sum=(v,key)=>v.reduce((s,x)=>s+x[key],0),inc=sum(traces,'increment'),area=sum(traces,'temperature_area'),dur=c.drain_stop_s-35;
 close(inc,m.increment_J_proxy,'Same-window work increment');close(conf.baseline*dur,m.baseline_J_proxy,'Unchanged common baseline');close(inc+conf.baseline*dur,m.total_J_proxy,'Total including baseline');
 const last=traces.at(-1);need(last.end_ns===Math.round(c.drain_stop_s*1e9),'Exact common drain boundary');
 const tail=H*conf.idle_tail_s*last.next_state.shared_z;close(inc+tail,m.full_tail_increment_J_proxy,'Observed-window work plus activation tail');
 const activeAtDrain=q.filter(x=>x.dispatch_ns!=null&&x.dispatch_ns/1e9<c.drain_stop_s&&(x.available_ns==null||x.available_ns/1e9>c.drain_stop_s));
 if(activeAtDrain.length)flags.push({label:row.label,reason:'active work remains at drain; reported tail excludes unobserved remaining job energy',count:activeAtDrain.length});
 const passive=conf.idle_c*dur+(c.temperature_c-conf.idle_c)*conf.thermal_tau_s*(-Math.expm1(-dur/conf.thermal_tau_s)),heat=Math.max(0,area-passive),peak=Math.max(...traces.map(x=>x.peak));
 close(heat,m.heat_area_proxy,'Heat above passive cooling');close(sum(work,'temperature_area')/(c.service_stop_s-35),m.mean_AP_c,'Exact same-window mean thermal proxy');
 const losses=['U','N'].map(role=>answered.filter(x=>x.priority===role).reduce((s,x)=>{let late=Math.max(0,(x.response_ns-x.deadline_ns)/1e9);return s+Number(late>1e-9)+.2*Math.min(5,late/Math.max(.05,(x.deadline_ns-x.scheduled_arrival_ns)/1e9));},0)/c.n);
 const vector=[(inc+tail)/(c.n*.35),heat/(c.n*3)+.1*Math.max(0,peak-32)/5,...losses,m.response_missing/c.n];
 for(let i=0;i<5;i++)close(vector[i],m.cost_vector[i],'Five objective components');close(vector.reduce((s,x,i)=>s+x*[.5,.5,8,4,30][i],0),m.objective,'Fixed weighted objective');
 for(const key of ['C_CPU','C_GPU','D_CPU','D_GPU'])close(q.filter(x=>x.task+'_'+x.route===key).length,m.route_counts[key],'Route counts including nondispatch denominator');
}
const value={status:'PASS_INDEPENDENT_ALL_REQUEST_METRICS_AND_OBJECTIVE',checks,max_absolute_difference:maxError,rows:result.rows.length,
 result_sha256:sha(path.join(out,'RESULT.json')),active_at_drain_flags:flags,new_environment_START:0,physical_accuracy_verified:false};
fs.writeFileSync(path.join(out,'SAVED_METRIC_AUDIT.json'),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({checks,maxError,rows:result.rows.length,activeAtDrainFlags:flags.length}));
