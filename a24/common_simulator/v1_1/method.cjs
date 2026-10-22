'use strict';
const {Engine}=require('../v1/engine.cjs'),{VERSION,ROUTES,FIFO,EDF,legal,validateSnapshot}=require('../v1/contract.cjs');
const MAX_ACTIONS=27,WIDTH=50;
const FEATURE_NAMES=['bias','dispatch','wait','event_wait','CPU','GPU','NPU','classification','urgent','age_10s','slack_10s','occupied_2s','response_2s','ttl_10s','ready_32','urgent_ready_32','owners_4','free_CPU_fraction','free_GPU_fraction','free_NPU_fraction','temperature_above_ambient_10C','power_energy_scale','cost_energy','cost_heat','cost_urgent','cost_normal','cost_unfinished','end_AP_above_ambient','peak_AP_above_ambient','forecast_span_30s','weighted_score_10','wait_seconds','wait_used_30s','CPU_owners_fraction','GPU_owners_fraction','NPU_owners_fraction','visible_32','horizon_reduced','steps_800','ATC_5','candidate_rank','CPU_nominal_response','GPU_nominal_response','NPU_nominal_response','CPU_supported','GPU_supported','NPU_supported','oldest_age_10s','min_slack_10s','same_class_ready_32'];
if(FEATURE_NAMES.length!==WIDTH)throw Error('Shared feature schema');
const compress=x=>Math.abs(x)<=5?x:Math.sign(x)*(5+Math.log1p(Math.abs(x)-5));
function estimate(profile,s,q,route){
 const phases=profile.nominalPhases(q,route,s.sensor.temperature_c),phys=profile.fromPublic(s.sensor.cost_state);
 let occupied=0,response=null;
 for(let k=0;k<phases.length;k++){const o={...q,route,stage:k,phases,progress:0},owners=s.owners.map(x=>({...x,phases:profile.nominalPhases(x,x.route,s.sensor.temperature_c)}));owners.push(o);const cpus=new Set(owners.map(x=>x.id));const rate=profile.rate(o,owners,cpus,phys,0);if(!(rate>0&&Number.isFinite(rate)))throw Error('Nominal rate');if(Number.isFinite(phases[k].response_at))response=occupied+phases[k].response_at/rate;occupied+=phases[k].work/rate;}
 if(response===null)throw Error('Explicit nominal response marker');return {occupied,response};
}
function baseline(profile,mode){if(!['FIFO','EDF','LSF','RR'].includes(mode))throw Error('Explicit baseline mode');let turn='C';return s=>{
 validateSnapshot(profile,s);
 const possible=s.queue.filter(q=>profile.allowed[q.task].some(r=>legal(profile,q,r,s.owners)));if(!possible.length)return {kind:'RESOURCE_WAIT'};
 const pool=mode==='RR'?(possible.filter(q=>q.task===turn).length?possible.filter(q=>q.task===turn):possible):possible;
 const q=pool.slice().sort(mode==='EDF'?EDF:mode==='LSF'?(a,b)=>{const pred=q=>Math.min(...profile.allowed[q.task].filter(r=>legal(profile,q,r,s.owners)).map(r=>estimate(profile,s,q,r).response));return a.deadline_s-pred(a)-(b.deadline_s-pred(b))||FIFO(a,b);}:FIFO)[0];
 const route=profile.allowed[q.task].filter(r=>legal(profile,q,r,s.owners)).map(r=>({r,latency:estimate(profile,s,q,r).response})).sort((a,b)=>a.latency-b.latency||a.r.localeCompare(b.r))[0].r;
 if(mode==='RR')turn=q.task==='C'?'D':'C';return {kind:'DISPATCH',id:q.id,route};
};}
function candidates(profile,s){
 validateSnapshot(profile,s);
 const queue=s.queue.slice().sort(EDF),pairs=[];for(const q of queue)for(const r of profile.allowed[q.task])if(legal(profile,q,r,s.owners))pairs.push({q,route:r,...estimate(profile,s,q,r)});
 if(!pairs.length)return {actions:[],visible:[],selected:[],pairs:[]};
 const mean=pairs.reduce((a,b)=>a+b.occupied,0)/pairs.length;
 for(const p of pairs)p.ATC=Math.log((p.q.priority==='U'?2:1)/Math.max(1e-9,p.occupied))-Math.max(0,p.q.deadline_s-s.time_s-p.response)/(2*Math.max(1e-9,mean));
 pairs.sort((a,b)=>b.ATC-a.ATC||FIFO(a.q,b.q)||a.response-b.response||a.route.localeCompare(b.route));
 const groups=new Map;for(const q of queue.slice().sort(FIFO)){const k=q.task+'|'+q.priority;if(!groups.has(k))groups.set(k,[]);groups.get(k).push(q);}const rows=[...groups].sort((a,b)=>a[0].localeCompare(b[0])).map(x=>x[1]);
 const ids=new Set;for(const q of [queue[0],...rows.flatMap(x=>[x[0],x.at(-1)]),...pairs.slice(0,6).map(x=>x.q),...queue]){if(ids.size>=8)break;ids.add(q.id);}
 const selected=queue.filter(q=>ids.has(q.id)),visibleIDs=new Set(ids);
 for(let k=0;k<queue.length&&visibleIDs.size<Math.min(32,queue.length);k++)for(const row of rows)for(const q of [row[k],row[row.length-1-k]])if(q&&visibleIDs.size<32)visibleIDs.add(q.id);
 const actions=selected.flatMap(q=>profile.allowed[q.task].filter(r=>legal(profile,q,r,s.owners)).map(route=>({kind:'DISPATCH',id:q.id,route})));
 for(const wait_s of [.02,.05])if(s.time_s+wait_s<s.dispatch_stop_s)actions.push({kind:'WAIT',wait_s});if(s.owners.length&&s.time_s<s.dispatch_stop_s)actions.push({kind:'WAIT_EVENT'});
 if(actions.length>MAX_ACTIONS)throw Error('Common action ABI');return {selected,visible:queue.filter(q=>visibleIDs.has(q.id)),pairs,actions};
}
function forecast(profile,s,action,visible,end,maxSteps=800){
 if(visible.some(q=>q.ready_s>s.time_s+1e-9||q.arrival_s>s.time_s+1e-9))throw Error('Future request in nominal input');
 const phys=profile.fromPublic(s.sensor.cost_state),startJ=phys.J,startH=phys.H;
 const e=new Engine(profile,visible,phys,{start_s:s.time_s,end_s:end,dispatch_stop_s:s.dispatch_stop_s,mode:'NOMINAL',nominal:true,event_cap:maxSteps});
 e.owners=s.owners.map(o=>{const phases=profile.nominalPhases(o,o.route,s.sensor.temperature_c);if(o.stage>=phases.length)throw Error('Public stage');return {...o,phases,progress:Math.min(phases[o.stage].work,o.phase_progress_public??0),public_progress:o.phase_progress_public??0,phase_elapsed_s:o.phase_elapsed_s,ticket:++e.ticket,available_s:null};});
 // Actual occupancy can outlast nominal work. settle() may therefore have already
 // delivered ANY original owner's AVAILABLE at the forecast origin. In that case
 // event wait is fulfilled at time zero; resume the same EDF continuation. This
 // never releases the actual owner or inserts a wait into the plant trajectory.
 const continuation=baseline(profile,'EDF');let first=true;e.run(state=>{if(first){first=false;if(action.kind==='WAIT_EVENT'&&s.owners.some(o=>!state.owners.some(v=>v.id===o.id)))return continuation(state);return action;}return continuation(state);});
 const all=[...visible,...s.owners],byID=new Map([...e.done,...e.owners].map(o=>[o.id,o])),span=Math.max(1e-9,e.time-s.time_s),n=Math.max(1,all.length),cost=[0,0,0,0,0];
 // Baseline subtraction is a physical-profile operation, shared cost formula follows.
 const baselinePower=profile.baselinePower??0;cost[0]=Math.max(0,e.physics.J-startJ-baselinePower*span)/n;
 cost[1]=Math.max(0,(e.physics.H-startH)/span-e.physics.ambient_c)/10;
 for(const q of all){const o=byID.get(q.id),response=o?.response_s??null,late=Math.max(0,(response??e.time)-q.deadline_s),g=q.priority==='U'?2:3,den=Math.max(1,all.filter(x=>x.priority===q.priority).length);cost[g]+=(Number(response===null||late>1e-9)+.02*Math.min(5,late/Math.max(.05,q.deadline_s-q.arrival_s)))/den;cost[4]+=Number(!o||o.available_s===null)/n;}
 const peak=Math.max(s.sensor.temperature_c,...e.trace.flatMap(t=>[t.T,t.next_T]));
 return {cost,AP_end:e.physics.temperature(),peak,H_s:e.time,steps:e.trace.length,capped:e.capped,visible_ids:all.map(q=>q.id).sort(),no_future_arrivals:true,no_future_latents:true};
}
function predictActions(profile,s,ctx,{max_steps=800}={}){
 const work=ctx.visible.reduce((sum,q)=>sum+Math.min(...profile.allowed[q.task].map(r=>estimate(profile,s,q,r).occupied)),0),requested=Math.max(s.time_s+1e-6,Math.min(s.dispatch_stop_s,s.time_s+Math.max(10,3*work+3*s.owners.length)));
 const first=ctx.actions.map(a=>forecast(profile,s,a,ctx.visible,requested,max_steps)),common=Math.min(...first.map(f=>f.H_s)),reduced=first.some(f=>f.capped);
 if(!(common>s.time_s+1e-10))throw Error('No positive common forecast horizon');
 const fs=reduced?ctx.actions.map(a=>forecast(profile,s,a,ctx.visible,common,max_steps)):first;
 for(const f of fs){if(f.capped||Math.abs(f.H_s-common)>1e-8)throw Error('Candidate common horizon incomplete');Object.assign(f,{capped:reduced,comparison_complete:true,horizon_reduced:reduced,requested_H_s:requested});}return fs;
}
function idleFilter(s,actions,fs,physical){const mask=physical.slice(),removed=[];
 if(!s.owners.length&&s.queue.length)for(let w=0;w<actions.length;w++)if(actions[w].kind==='WAIT')for(let d=0;d<actions.length;d++)if(actions[d].kind==='DISPATCH'){
  const a=fs[d],b=fs[w];if(a.capped||b.capped||!a.comparison_complete||!b.comparison_complete||Math.abs(a.H_s-b.H_s)>1e-8||JSON.stringify(a.visible_ids)!==JSON.stringify(b.visible_ids))continue;
  const va=[...a.cost,a.AP_end,a.peak],vb=[...b.cost,b.AP_end,b.peak];let strict=false,worse=false;
  for(let k=0;k<7;k++){const t=1e-9+1e-9*Math.max(Math.abs(va[k]),Math.abs(vb[k]));if(va[k]-vb[k]>t)worse=true;if(vb[k]-va[k]>t)strict=true;}
  if(!worse&&strict){mask[w]=false;removed.push({index:w,dominator:d});break;}
 }return {mask,removed};}
function encode(profile,s,options={}){
 const ctx=candidates(profile,s);if(!ctx.actions.length)return null;
 const forecasts=predictActions(profile,s,ctx,options),physical=Array(MAX_ACTIONS).fill(false);ctx.actions.forEach((a,i)=>physical[i]=true);
 const filtered=idleFilter(s,ctx.actions,forecasts,physical),mask=options.idle_filter===false?physical:filtered.mask;
 const scores=Array(MAX_ACTIONS).fill(0),x=Array.from({length:MAX_ACTIONS},()=>Array(WIDTH).fill(0));
 const free=r=>Math.max(0,(profile.owner_capacity[r]-s.owners.filter(o=>o.route===r).length)/Math.max(1,profile.owner_capacity[r]));
 for(let i=0;i<ctx.actions.length;i++){
  const a=ctx.actions[i],q=s.queue.find(q=>q.id===a.id)??ctx.selected[0],route=a.route??profile.allowed[q.task][0],pair=ctx.pairs.find(p=>p.q.id===q.id&&p.route===route)??{...estimate(profile,s,q,route),ATC:ctx.pairs[0].ATC};
  const f=forecasts[i],c=f.cost,score=c[0]/profile.energy_scale+c[1]+12*c[2]+6*c[3]+3*c[4];scores[i]=score;
  const nr=ROUTES.map(r=>profile.allowed[q.task].includes(r)?estimate(profile,s,q,r).response:0),supported=ROUTES.map(r=>Number(profile.allowed[q.task].includes(r))),own=ROUTES.map(r=>s.owners.filter(o=>o.route===r).length/Math.max(1,profile.owner_capacity[r]));
  const row=[1,Number(a.kind==='DISPATCH'),Number(a.kind==='WAIT'),Number(a.kind==='WAIT_EVENT'),...ROUTES.map(r=>Number(route===r)),Number(q.task==='C'),Number(q.priority==='U'),(s.time_s-q.arrival_s)/10,(q.deadline_s-s.time_s)/10,pair.occupied/2,pair.response/2,Math.max(.05,q.deadline_s-q.arrival_s)/10,s.queue.length/32,s.queue.filter(q=>q.priority==='U').length/32,s.owners.length/4,...ROUTES.map(free),(s.sensor.temperature_c-s.sensor.ambient_c)/10,s.sensor.power/profile.energy_scale,...c,(f.AP_end-s.sensor.ambient_c)/10,(f.peak-s.sensor.ambient_c)/10,(f.H_s-s.time_s)/30,score/10,a.wait_s??0,s.wait_used_s/30,...own,ctx.visible.length/32,Number(f.capped),f.steps/800,pair.ATC/5,ctx.selected.findIndex(v=>v.id===q.id)/Math.max(1,ctx.selected.length-1),...nr,...supported,Math.max(...s.queue.map(q=>s.time_s-q.arrival_s))/10,Math.min(...s.queue.map(q=>q.deadline_s-s.time_s))/10,s.queue.filter(v=>v.task===q.task).length/32];
  if(row.length!==WIDTH||!row.every(Number.isFinite))throw Error('Shared 50-feature ABI');x[i]=row.map(compress);
 }
 return {version:VERSION,feature_names:FEATURE_NAMES,actions:ctx.actions,x,mask,physical_mask:physical,scores,forecasts,idle_wait_guard:filtered,candidate_ids:ctx.selected.map(q=>q.id),visible_ids:ctx.visible.map(q=>q.id)};
}
function teacher(bank){return bank.actions.map((a,i)=>i).filter(i=>bank.mask[i]).sort((a,b)=>bank.scores[a]-bank.scores[b]||a-b)[0];}
function compatibleTargets(s,bank,index){const a=bank.actions[index],q=s.queue.find(q=>q.id===a.id);return bank.mask.map((allowed,i)=>{const b=bank.actions[i];if(!allowed||!b)return false;if(a.kind!=='DISPATCH')return JSON.stringify(a)===JSON.stringify(b);const v=s.queue.find(q=>q.id===b.id);return b.kind==='DISPATCH'&&b.route===a.route&&v.task===q.task&&v.priority===q.priority&&v.deadline_s===q.deadline_s;});}
module.exports={VERSION,MAX_ACTIONS,WIDTH,FEATURE_NAMES,estimate,baseline,candidates,forecast,predictActions,idleFilter,encode,teacher,compatibleTargets};
