const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/PROTECTED48_V2_20261016_01');
const b=fs.readFileSync(path.join(out,'RESULT.json')),d=JSON.parse(b),hash=crypto.createHash('sha256').update(b).digest('hex');
if(JSON.parse(fs.readFileSync(path.join(out,'COMPLETE.json'),'utf8')).result_sha256!==hash)throw Error('Terminal result pin');
const NEW='ROLLING_ATC_RL_PROTECTED48',EDF='EDF_CPU_FIRST',OLD='ROLLING_ATC_RL',CTRL='PROTECTION_ATC_COST_NO_RL';
function compare(cs,a,b){
 const pairs=cs.map(c=>{const x=c.metrics.find(r=>r.policy===a),y=c.metrics.find(r=>r.policy===b);return {index:c.index,label:c.label,
  total_J:x.total_J_proxy-y.total_J_proxy,total_percent:100*(x.total_J_proxy/y.total_J_proxy-1),increment_J:x.increment_J_proxy-y.increment_J_proxy,increment_percent:100*(x.increment_J_proxy/y.increment_J_proxy-1),
  mean_AP_c:x.mean_AP_c-y.mean_AP_c,peak_AP_c:x.peak_AP_c-y.peak_AP_c,end_AP_c:x.end_AP_c-y.end_AP_c,
  on_time:x.on_time-y.on_time,missing:x.response_missing-y.response_missing,window_available:x.AVAILABLE_by_window_end-y.AVAILABLE_by_window_end,
  tardiness_s:x.total_tardiness_s===null||y.total_tardiness_s===null?null:x.total_tardiness_s-y.total_tardiness_s};});
 const stats={};for(const k of ['total_J','increment_J','mean_AP_c','peak_AP_c','end_AP_c']){const eps=k.includes('AP')?1e-6:1e-8;stats[k]={lower:pairs.filter(x=>x[k]<-eps).length,equal:pairs.filter(x=>Math.abs(x[k])<=eps).length,higher:pairs.filter(x=>x[k]>eps).length,mean:pairs.reduce((s,x)=>s+x[k],0)/pairs.length,min:Math.min(...pairs.map(x=>x[k])),max:Math.max(...pairs.map(x=>x[k]))};}
 stats.on_time={better:pairs.filter(x=>x.on_time>0).length,equal:pairs.filter(x=>x.on_time===0).length,worse:pairs.filter(x=>x.on_time<0).length,net:pairs.reduce((s,x)=>s+x.on_time,0)};
 return {policy:a,baseline:b,conditions:cs.length,stats,pairs};
}
function behavior(cs,p){let routes={},removed=0,calls=0,critical=0,fallback=0,wait=0,overlap=0;for(const c of cs){const r=c.rows.find(x=>x.policy===p);for(const [k,v]of Object.entries(r.route_counts))routes[k]=(routes[k]||0)+v;wait+=r.wait_s;overlap+=r.metrics.overlap_ns/1e9;for(const x of r.protection_decisions||[]){calls++;removed+=x.protection.removed_actions;critical+=x.protection.critical_request!==null;fallback+=x.protection.nominal_recovery_fallback;}}
 return {policy:p,routes,wait_seconds_sum:wait,owner_overlap_seconds_sum:overlap,actor_calls:calls,masked_candidate_occurrences:removed,critical_calls:critical,recovery_calls:fallback};}
const r={schema:'A24-protected48-saved-analysis-v1',result_sha256:hash,selected:d.selected,updates:d.updates,optimizer_steps:d.optimizer_steps,
 comparisons:{fresh_new_EDF:compare(d.fresh_cases,NEW,EDF),fresh_old_EDF:compare(d.fresh_cases,OLD,EDF),fresh_new_old:compare(d.fresh_cases,NEW,OLD),historical_new_EDF:compare(d.historical_cases,NEW,EDF),historical_new_old:compare(d.historical_cases,NEW,OLD),mechanism_new_noNN:compare(d.mechanism_cases,NEW,CTRL)},
 fresh_behavior:[EDF,OLD,NEW].map(p=>behavior(d.fresh_cases,p)),historical_behavior:[EDF,OLD,NEW].map(p=>behavior(d.historical_cases,p)),
 targets:{no_service_harm:d.targets.filter(x=>x.no_service_harm).length,both_heat_and_total_lower:d.targets.filter(x=>x.both_heat_and_total_lower).length,total_10pct_AP_0_5:d.targets.filter(x=>x.target_total_10pct_AP_0_5).length,conditions:d.targets.length},
 aggregate:d.aggregate,physical_goal_validated:false,measured_J:null,CI:null,new_environment:0,new_fit:0,utc:new Date().toISOString()};
fs.writeFileSync(path.join(out,'ANALYSIS.json'),JSON.stringify(r,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({targets:r.targets,aggregate:r.aggregate,fresh_new_EDF:r.comparisons.fresh_new_EDF.stats,control:r.comparisons.mechanism_new_noNN.stats}));
