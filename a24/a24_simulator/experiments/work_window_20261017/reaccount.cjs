'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),zlib=require('zlib'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const load=p=>JSON.parse(p.endsWith('.gz')?zlib.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p));
const need=(x,s)=>{if(!x)throw Error(s);};
const save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx'});
function partial(tr,d,c,H){
 const T=tr.state.temperature_c,z=tr.state.shared_z,dyn=tr.dynamic/tr.dt,tt=c.thermal_tau_s,R=c.thermal_resistance;
 let shared=0,forcing=0,forcingArea=0,z1=z;
 const a=-Math.expm1(-d/tt),e=Math.exp(-d/tt);
 if(tr.active.length){shared=H*d;forcing=R*(dyn+H)*a;forcingArea=R*(dyn+H)*(d-tt*a);z1=1;}
 else if(c.idle_tail_s){const tz=c.idle_tail_s,b=-Math.expm1(-d/tz),factor=R*H*z*tz/(tz-tt);shared=H*z*tz*b;z1=z*Math.exp(-d/tz);forcing=factor*(Math.exp(-d/tz)-e);forcingArea=factor*(tz*b-tt*a);}
 const end=c.idle_c+(T-c.idle_c)*e+forcing;
 return {increment:dyn*d+shared,temperature_area:c.idle_c*d+(T-c.idle_c)*tt*a+forcingArea,temperature_c:end,shared_z:z1};
}
function integrate(raw,endNs,c,H){
 let inc=0,area=0,coverage=0,partialCount=0;
 for(const t of raw.trace){if(t.start_ns>=endNs)break;const durationNs=Math.min(endNs,t.end_ns)-t.start_ns;if(durationNs<=0)continue;
  coverage+=durationNs;
  if(t.end_ns<=endNs){inc+=t.increment;area+=t.temperature_area;}
  else {const x=partial(t,durationNs/1e9,c,H);inc+=x.increment;area+=x.temperature_area;partialCount++;}
 }
 need(Math.abs(coverage-(endNs-35e9))<=1,'Complete prefix coverage');
 const duration=(endNs-35e9)/1e9,base=c.baseline*duration;
 const answered=raw.requests.filter(q=>q.response_ns!=null&&q.response_ns<=endNs),completed=raw.requests.filter(q=>q.available_ns!=null&&q.available_ns<=endNs);
 return {end_ns:endNs,duration_s:duration,baseline_J_proxy:base,increment_J_proxy:inc,total_J_proxy:base+inc,baseline_fraction:base/(base+inc),mean_AP_c:area/duration,temperature_area:area,
  planned:raw.requests.length,on_time:answered.filter(q=>q.response_ns<=q.deadline_ns).length,urgent_on_time:answered.filter(q=>q.priority==='U'&&q.response_ns<=q.deadline_ns).length,
  response_missing:raw.requests.length-answered.length,incomplete:raw.requests.length-completed.length,partial_intervals:partialCount};
}
const eligible=(m,ref)=>m.incomplete===0&&m.response_missing===0&&m.on_time>=ref.on_time&&m.urgent_on_time>=ref.urgent_on_time;
function main(){
 const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output);
 for(const p of [...op.sources,...op.inputs])need(sha(path.join(repo,p.path))===p.sha256,'Immutable source/input '+p.path);
 need(!fs.existsSync(out),'Output exists; preserve earlier attempt');fs.mkdirSync(out);
 save(path.join(out,'START.json'),{utc:new Date().toISOString(),HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),uncommitted_changes:!!cp.execFileSync('git',['status','--porcelain'],{cwd:repo,encoding:'utf8'}).trim(),command:process.argv,operation_sha256:sha(path.join(__dirname,'OPERATION.json')),native_START:0});
 const old=read(path.join(root,op.parent,'RESULT.json')),newer=read(path.join(root,op.diagnosis,'RESULT.json')),oldOp=read(path.join(root,'experiments/coupled_345_20261017/OPERATION.json')),c=oldOp.physics;
 const bounds=read(path.join(root,op.diagnosis,'BOUNDS.json')).cases,design=read(path.join(root,'experiments/coupled_345_20261017/INPUTS.json')).fresh;
 const H=bounds[0].coefficients.shared,rows=[...old.rows.filter(x=>x.kind==='FRESH'),...newer.rows.filter(x=>x.kind==='FULL_WITNESS')].map(r=>{
  const rawPath=path.join(root,r.kind==='FRESH'?op.parent:op.diagnosis,r.label+'.raw.json.gz');need(sha(rawPath)===r.raw_sha256,'Saved native SHA');const raw=load(rawPath);
  const result=raw.result,complete=result.requests.every(q=>Number.isFinite(q.available_ns));
  return {source:r,raw:result,rawPath:path.relative(repo,rawPath).replaceAll('\\','/'),last:complete?Math.max(...result.requests.map(q=>q.available_ns)):null,policy:r.label.slice(r.case.length+1)};
 });
 const perCase=[],allRows=[];let maxOldError=0;
 for(const caseSpec of design){
  const local=rows.filter(r=>r.source.case===caseSpec.id),main=local.filter(r=>r.source.kind==='FRESH');need(main.length===8&&op.primary_policies.every(p=>main.some(r=>r.policy===p)),'Fixed8 policy roster');
  const common=main.some(r=>r.last==null)?Math.round(caseSpec.drain_stop_s*1e9):Math.max(...main.map(r=>r.last));need(common<=Math.round(caseSpec.drain_stop_s*1e9),'Observed task end within old accounting window');
  const b=bounds.find(x=>x.case===caseSpec.id),bank=load(path.join(root,op.diagnosis,caseSpec.id+'.BANK.json.gz')).jobs;
  const minWork=bank.map(j=>({release:j.queue_entry_ns/1e9,work:Math.min(...['CPU','GPU'].map(r=>j.routes[r].stages_ns.reduce((s,t)=>s+t,0)/1e9))}));
  const earliest=Math.max(35,...minWork.map(x=>x.release+x.work),...minWork.map(x=>x.release+minWork.filter(z=>z.release>=x.release-1e-10).reduce((s,z)=>s+z.work,0)/2));
  const workLower=b.total_energy_lower-b.baseline,completionLower=c.baseline*Math.max(0,earliest-35-1e-6)+workLower;
  const saved=local.map(x=>{
   const original=integrate(x.raw,Math.round(caseSpec.drain_stop_s*1e9),c,H),commonM=integrate(x.raw,common,c,H),own=integrate(x.raw,x.last??Math.round(caseSpec.drain_stop_s*1e9),c,H);
   for(const [a,z] of [[original.total_J_proxy,x.source.metrics.total_J_proxy],[original.increment_J_proxy,x.source.metrics.increment_J_proxy]]){maxOldError=Math.max(maxOldError,Math.abs(a-z));need(Math.abs(a-z)<2e-7,'Original saved energy reproduced');}
   const ownTail=H*c.idle_tail_s;
   need(x.last==null||earliest<=x.last/1e9+2e-7,'Optimistic completion-time lower bound');
   if(x.last!=null&&eligible(own,b.reference))need(completionLower<=own.total_J_proxy+2e-7,'Completion energy lower below feasible schedule');
   const row={case:caseSpec.id,policy:x.policy,source_kind:x.source.kind,label:x.source.label,raw_path:x.rawPath,raw_sha256:x.source.raw_sha256,last_available_ns:x.last,original,
    common:commonM,completion:own,original_reported_mean_AP_c:x.source.metrics.mean_AP_c,
    original_mean_AP_window:[35,caseSpec.service_stop_s],post_complete_original_s:x.last==null?null:caseSpec.drain_stop_s-x.last/1e9,
    post_completion_activation_tail_J_proxy:x.last==null?null:ownTail,source_metrics_unchanged:x.source.metrics};allRows.push(row);return row;
  });
  const ref=saved.find(r=>r.policy==='EDF'),picks={};
  for(const window of ['original','common','completion']){
   const candidates=saved.filter(x=>eligible(x[window],ref[window]));
   const best=candidates.reduce((a,z)=>z[window].total_J_proxy<a[window].total_J_proxy?z:a);
   picks[window]={label:best.label,metrics:best[window],reference:ref[window],saving_percent:100*(1-best[window].total_J_proxy/ref[window].total_J_proxy)};
  }
  const commonLower=c.baseline*(common/1e9-35)+workLower;
  need(commonLower<=ref.common.total_J_proxy+2e-7,'Common bound below feasible EDF');
  perCase.push({case:caseSpec.id,common_end_ns:common,common_duration_s:common/1e9-35,latest_primary_policy:main.filter(r=>r.last===common).map(r=>r.policy),reference:ref,
   work_lower:workLower,completion_time_lower_s:earliest,completion_time_numerical_margin_s:1e-6,common_energy_lower:commonLower,completion_energy_lower:completionLower,
   common_upper_percent:100*(1-commonLower/ref.common.total_J_proxy),completion_upper_percent:100*(1-completionLower/ref.completion.total_J_proxy),picks});
 }
 const sum=(items,f)=>items.reduce((s,x)=>s+f(x),0),summary={};
 for(const window of ['original','common','completion']){
  const refs=perCase.map(x=>x.reference[window]),B=sum(refs,x=>x.total_J_proxy),base=sum(refs,x=>x.baseline_J_proxy),U=sum(perCase,x=>x.picks[window].metrics.total_J_proxy);
  summary[window]={EDF_mean_total_J_proxy:B/12,EDF_mean_baseline_J_proxy:base/12,EDF_mean_increment_J_proxy:(B-base)/12,EDF_baseline_fraction:base/B,EDF_mean_duration_s:sum(refs,x=>x.duration_s)/12,
   found_feasible_portfolio_mean_total_J_proxy:U/12,found_feasible_portfolio_saving_percent:100*(1-U/B),
   found_is_posthoc_per_case_portfolio:true};
  if(window!=='original'){const L=sum(perCase,x=>x[window+'_energy_lower']);summary[window].optimistic_mean_energy_lower=L/12;summary[window].maximum_mean_saving_percent=100*(1-L/B);summary[window].ten_percent_impossible_in_relaxation=100*(1-L/B)<10;}
 }
 const policies=Object.fromEntries([...op.primary_policies,'TRUTH_EXACT','TRUTH_ATC','ENERGY_ROUTE'].map(p=>{
  const rr=allRows.filter(r=>r.policy===p),m={policy:p,cases:rr.length};for(const window of ['original','common','completion'])m[window]={mean_total:sum(rr,r=>r[window].total_J_proxy)/rr.length,mean_increment:sum(rr,r=>r[window].increment_J_proxy)/rr.length,
   mean_AP:sum(rr,r=>r[window].mean_AP_c)/rr.length,on_time:sum(rr,r=>r[window].on_time),urgent_on_time:sum(rr,r=>r[window].urgent_on_time),response_missing:sum(rr,r=>r[window].response_missing),incomplete:sum(rr,r=>r[window].incomplete),mean_duration_s:sum(rr,r=>r[window].duration_s)/rr.length};return [p,m];}));
 for(const p of [...op.sources,...op.inputs])need(sha(path.join(repo,p.path))===p.sha256,'Sources unchanged at end');
 const result={schema:'A24-saved-work-window-result-v1',utc:new Date().toISOString(),summary,policies,cases:perCase,rows:allRows,partial_integrations:sum(allRows,r=>r.common.partial_intervals+r.completion.partial_intervals+r.original.partial_intervals),
  original_energy_max_error:maxOldError,source_rows:132,native_START:0,training:0,fit:0,optimization_solves:0,measured_J:null,physical_accuracy_verified:false,
  metrics_are_posthoc:true,common_endpoint_selected_from_all8_original_policies:true,completion_mean_AP_is_different_duration:true};
 save(path.join(out,'RESULT.json'),result);save(path.join(out,'COMPLETE.json'),{utc:new Date().toISOString(),result_sha256:sha(path.join(out,'RESULT.json')),saved_schedules:132,native_START:0,new_reservation:0});
 console.log(JSON.stringify({summary,partial_integrations:result.partial_integrations,original_energy_max_error:maxOldError},null,2));
}
if(require.main===module)main();module.exports={partial,integrate};
