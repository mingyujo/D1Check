'use strict';
// Independent RK4 integration of every truncated interval, without job execution.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),zlib=require('zlib'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output),a=read(path.join(out,'RESULT.json')),terminal=read(path.join(out,'COMPLETE.json'));
let checks=0,maxError=0,partialChecks=0;const need=(x,s)=>{checks++;if(!x)throw Error(s);},close=(x,y,s,tol=2e-7)=>{maxError=Math.max(maxError,Math.abs(x-y));need(Math.abs(x-y)<tol,s);};
for(const p of [...op.sources,...op.inputs])need(sha(path.join(repo,p.path))===p.sha256,'Input/source SHA');need(sha(path.join(out,'RESULT.json'))===terminal.result_sha256,'Terminal SHA');
const c=read(path.join(root,'experiments/coupled_345_20261017/OPERATION.json')).physics,H=read(path.join(root,op.diagnosis,'BOUNDS.json')).cases[0].coefficients.shared;
function rk(tr,d){
 const dyn=tr.dynamic/tr.dt,active=tr.active.length>0;
 let y=[tr.state.temperature_c,tr.state.shared_z,0,0],n=Math.max(1,Math.ceil(d/.005)),h=d/n;
 const f=v=>{const P=dyn+H*(active?1:v[1]);return [(-(v[0]-c.idle_c)+c.thermal_resistance*P)/c.thermal_tau_s,active?0:-v[1]/c.idle_tail_s,P,v[0]];};
 for(let i=0;i<n;i++){const k1=f(y),k2=f(y.map((v,j)=>v+h*k1[j]/2)),k3=f(y.map((v,j)=>v+h*k2[j]/2)),k4=f(y.map((v,j)=>v+h*k3[j]));y=y.map((v,j)=>v+h*(k1[j]+2*k2[j]+2*k3[j]+k4[j])/6);}
 return {increment:y[2],area:y[3]};
}
for(const row of a.rows){
 const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(repo,row.raw_path)))).result;need(sha(path.join(repo,row.raw_path))===row.raw_sha256,'Exact native raw');
 for(const window of ['original','common','completion']){
  const m=row[window];let E=0,A=0,covered=0;
  for(const tr of raw.trace){if(tr.start_ns>=m.end_ns)break;const ns=Math.min(tr.end_ns,m.end_ns)-tr.start_ns;if(ns<=0)continue;covered+=ns;
   if(tr.end_ns<=m.end_ns){E+=tr.increment;A+=tr.temperature_area;}else {const x=rk(tr,ns/1e9);E+=x.increment;A+=x.area;partialChecks++;}
  }
  need(covered===m.end_ns-35e9,'Contiguous time coverage');close(E,m.increment_J_proxy,'Independent partial power');close(A,m.temperature_area,'Independent RC area');close(E+c.baseline*(m.end_ns/1e9-35),m.total_J_proxy,'Baseline and increment');
  const done=raw.requests.filter(q=>q.available_ns!=null&&q.available_ns<=m.end_ns),responded=raw.requests.filter(q=>q.response_ns!=null&&q.response_ns<=m.end_ns);
  need(m.incomplete===raw.requests.length-done.length&&m.response_missing===raw.requests.length-responded.length,'All denominators retained');need(m.on_time===responded.filter(q=>q.response_ns<=q.deadline_ns).length,'Deadline count');
 }
 const source=row.source_metrics_unchanged;close(row.original.total_J_proxy,source.total_J_proxy,'Original metric recovered');
 if(row.last_available_ns!=null){close(row.original.increment_J_proxy-row.completion.increment_J_proxy,H*c.idle_tail_s,'Full decay tail accounted',2e-7);need(row.completion.incomplete===0,'Own completion excludes no job');}
 if(row.source_kind==='FRESH')need(row.common.incomplete===0,'Every original policy finishes within common cut');
}
for(const cc of a.cases){const rr=a.rows.filter(r=>r.case===cc.case&&r.source_kind==='FRESH');need(cc.common_end_ns===Math.max(...rr.map(r=>r.last_available_ns)),'Common cut fixed across original8');
 for(const window of ['common','completion']){const ref=cc.reference[window],pick=a.rows.find(r=>r.label===cc.picks[window].label)[window];need(pick.incomplete===0&&pick.response_missing===0&&pick.on_time>=ref.on_time&&pick.urgent_on_time>=ref.urgent_on_time,'Selected witness SLA');}
}
const audit={status:'PASS_SAVED_WINDOW_REACCOUNT',utc:new Date().toISOString(),command:process.argv,HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),uncommitted_changes:!!cp.execFileSync('git',['status','--porcelain'],{cwd:repo,encoding:'utf8'}).trim(),checks,max_absolute_error:maxError,independent_RK4_partial_intervals:partialChecks,result_sha256:sha(path.join(out,'RESULT.json')),native_START:0,training:0,fit:0,new_reservation:0};
fs.writeFileSync(path.join(out,'AUDIT.json'),JSON.stringify(audit,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(audit,null,2));
