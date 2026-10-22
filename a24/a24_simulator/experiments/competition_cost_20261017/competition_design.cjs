(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.A24Competition=factory();})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const SPEC={schema:'A24-competition-input-design-v1',request_count:48,mixes:[.25,.5,.75],patterns:['staggered_wave','clustered_recovery'],reference_loads:[.65,.95],
  reference_occupancy_s:{C:.255213692,D:.568107423},reference_origin:'same C_GPU/D_CPU reference as frozen bulk_design; conservative design proxy, not true 2-lane utilization',
  base_deadline_s:{C:2.2,D:5},deadline_tiers:[.32,.65,1],urgent_multiplier:.7,urgent_fraction_per_task:.25,
  wave_size:6,start_s:35,common_window:'first arrival to last arrival+15s',physical_scope:'C/D choose CPU/GPU, max2, nonpreemptive until AVAILABLE',
  filter_by_policy_result:false,legacy24_preserved:true};
 function rng(seed){let x=seed>>>0;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296;};}
 function shuffle(a,r){for(let i=a.length-1;i>0;i--){const j=Math.floor(r()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
 function build(mix,pattern,load,seed){
  if(!SPEC.mixes.includes(mix)||!SPEC.patterns.includes(pattern)||!SPEC.reference_loads.includes(load)||!Number.isInteger(seed)||seed<=0||seed>=2147483648)throw Error('Registered design values required');
  const random=rng(seed),tasks=shuffle([...Array(Math.round(48*mix)).fill('C'),...Array(48-Math.round(48*mix)).fill('D')],random),roles={},tiers={};
  for(const task of ['C','D']){
   const ids=shuffle(tasks.flatMap((t,i)=>t===task?[i]:[]),random);
   ids.forEach((id,j)=>{roles[id]=j<ids.length*.25?'U':'N';tiers[id]=SPEC.deadline_tiers[(j+(task==='D'?1:0))%3];});
  }
  let origin=SPEC.start_s;const requests=[];
  for(let w=0;w<8;w++){
   const ids=Array.from({length:6},(_,j)=>w*6+j),demand=ids.reduce((s,i)=>s+SPEC.reference_occupancy_s[tasks[i]],0);
   const period=Math.max(1.25,demand/(2*load));
   const offsets=pattern==='staggered_wave'?[0,.08,.23,.41,.70,1.0]:[0,0,.06,.06,.12,.12];
   for(let j=0;j<6;j++){
    const i=ids[j],task=tasks[i],arrival=+(origin+offsets[j]).toFixed(8),priority=roles[i];
    const relative=SPEC.base_deadline_s[task]*tiers[i]*(priority==='U'?.7:1);
    if(relative<SPEC.reference_occupancy_s[task]*1.25)throw Error('Unloaded conservative reference feasibility');
    requests.push({ordinal:i,profile:task+'_M128',priority,arrival_s:arrival,deadline_s:+(arrival+relative).toFixed(8)});
   }
   origin+=period*(pattern==='clustered_recovery'&&w%3===2?1.5:1);
  }
  return {label:'경쟁48 · C'+mix*100+'% · '+pattern+' · reference '+load+' · seed '+seed,
   condition:{n:48,mix,pattern,reference_load:load,seed,deadline_tiers:SPEC.deadline_tiers,posthoc_policy_filter:false},
   input:{requests,seed,rl_seed:20261028,initial_context:'M128',alpha:1}};
 }
 function generate(seed){const cases=[];for(const m of SPEC.mixes)for(const p of SPEC.patterns)for(const l of SPEC.reference_loads)cases.push({...build(m,p,l,seed),index:cases.length});return cases;}
 function audit(c){
  const q=c.input.requests,by={C:{U:0,N:0},D:{U:0,N:0}};let inversions=0,nearDifferentDue=0;
  q.forEach((r,i)=>{if(r.ordinal!==i||!['C_M128','D_M128'].includes(r.profile)||r.arrival_s<0||r.deadline_s<=r.arrival_s||r.deadline_s>210)throw Error('Public request contract');by[r.profile[0]][r.priority]++;});
  for(let i=0;i<q.length;i++)for(let j=i+1;j<q.length;j++){
   if(q[i].arrival_s<=q[j].arrival_s&&q[i].deadline_s>q[j].deadline_s)inversions++;
   if(Math.abs(q[i].arrival_s-q[j].arrival_s)<=.25&&q[i].deadline_s!==q[j].deadline_s)nearDifferentDue++;
  }
  return {planned:q.length,by_task_priority:by,absolute_deadline_order_inversions:inversions,near_arrival_different_deadline_pairs:nearDifferentDue,
   common_work_window_s:[Math.min(...q.map(r=>r.arrival_s)),Math.min(180,Math.max(...q.map(r=>r.arrival_s))+15)],
   static_input_diagnostic_only:true,actual_queue_competition_verified:false};
 }
 return {SPEC,generate,audit,build};
});
