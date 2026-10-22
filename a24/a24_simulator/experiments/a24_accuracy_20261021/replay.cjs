'use strict';
// Force the saved measured schedule through the actual current A24 physics.
// No fitting, queue scheduling, policy rollout, latent draw or target feedback.
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto');
const H=__dirname,R=path.resolve(H,'../../..'),O=path.join(R,'a24_simulator/results/A24_ACCURACY_20261021_02');
const {A24Physics}=require(path.join(R,'common_simulator/v1/profiles.cjs'));
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const packet=read(path.join(O,'INPUTS.json')),reg=read(path.join(O,'REGISTRATION.json'));
for(const p of [reg.inputs,...reg.sources])if(hash(path.join(R,p.path))!==p.sha256)throw Error('Changed source '+p.path);
const newfile=path.join(O,'PREDICTIONS.json.gz');if(fs.existsSync(newfile))throw Error('Consumed output');
const results=[],legacy=new Map(packet.legacy_power.map(s=>['A24_'+s.id,s]));
for(const c of packet.cases){
 const old=legacy.get(c.session),lo=Math.max(35,c.observations[0].t,old?.power_t[0]??35),hi=Math.min(c.observations.at(-1).t,old?.power_t.at(-1)??Infinity,c.activity_end_s);
 const powerWindows=old?[
  {name:'matched_AP_power',lo,hi},
  {name:'registered',lo:35,hi:old.common_end_s??120},
  {name:'work_present',lo:35,hi:old.last_lane_s??35},
  {name:'recovery_observed',lo:Math.max(35,old.last_lane_s??35),hi}
 ].filter(w=>w.hi>w.lo&&w.hi<=old.power_t.at(-1)&&w.hi<=c.activity_end_s):[];
 const times=[...new Set([...c.observations.map(o=>o.t),...powerWindows.flatMap(w=>[w.lo,w.hi])])].sort((a,b)=>a-b);
 const events=c.owners.flatMap(o=>[{t:o.start_s,type:1,o},{t:o.end_s,type:0,o}]).sort((a,b)=>a.t-b.t||a.type-b.type||a.o.id.localeCompare(b.o.id));
 const modes=[];
 for(const tick of [.05,.1])for(const initial of ['observed_pre','reference_26']){
  const p=new A24Physics(packet.profile);p.T=initial==='observed_pre'?c.initial_c:26;
  const active=new Map();let event=0,time=35,steps=0;
  while(event<events.length&&events[event].t<=35){const e=events[event++];if(e.type)active.set(e.o.id,e.o);else active.delete(e.o.id);}
  if(active.size)p.z=1;
  const snapshots=new Map();
  for(const query of times){
   while(time<query-1e-10){
    while(event<events.length&&events[event].t<=time+1e-10){const e=events[event++];if(e.type){active.set(e.o.id,e.o);p.z=1;}else active.delete(e.o.id);}
    const end=Math.min(query,time+tick,event<events.length?events[event].t:Infinity);
    if(end<=time)throw Error('Nonprogress');
    p.advance(end-time,[...active.values()]);time=end;steps++;
    if(!Number.isFinite(p.T+p.J+p.H))throw Error('Invalid trajectory');
   }
   snapshots.set(query,{T:p.T,J:p.J,H:p.H});
  }
  modes.push({tick,initial,steps,AP:c.observations.map(o=>snapshots.get(o.t).T),
   power_windows:powerWindows.map(w=>({...w,predicted_J_proxy:snapshots.get(w.hi).J-snapshots.get(w.lo).J})),
   end_state:p.exportState()});
 }
 results.push({session:c.session,modes});
}
for(const p of [reg.inputs,...reg.sources])if(hash(path.join(R,p.path))!==p.sha256)throw Error('Source drift '+p.path);
fs.writeFileSync(newfile,zlib.gzipSync(JSON.stringify({status:'SAVED_CONDITIONAL_REPLAY_COMPLETE',cases:results,source_unchanged:true,policy_environments:0,fits:0,phone_measurements:0})),{flag:'wx'});
process.stdout.write(JSON.stringify({status:'COMPLETE',cases:results.length,modes:results.length*4,bytes:fs.statSync(newfile).size})+'\n');
