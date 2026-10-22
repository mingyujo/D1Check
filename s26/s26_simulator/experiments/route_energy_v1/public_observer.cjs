'use strict';
// Incremental replay of observed activity only. Keep the left limit at each
// snapshot, then clone and add the same artificial right-end zero as fromPast.
// No actual latent durations/progress or future source events enter this cache.
const {Physics,proxy}=require('./physics.cjs'),{steps}=require('../capacity_power_v1/replay.cjs');
function past(obs,pm,tm,state){const t=obs.time,ints=obs.cost_state.activity9.intervals;let p=state.publicObserver;
 if(!p){p=new Physics(pm,tm,obs.physics_context);for(const [at,v]of steps(ints)){if(at>=t)break;p.advance(at-p.time);p.set(v);}p.advance(t-p.time);}
 else if(t<p.time)throw Error('Public observer time reversal');
 else if(t>p.time){const start=p.time,current=Array(9).fill(0),events=new Map;
  const add=(at,j,v)=>{if(at<=start||at>=t)return;if(!events.has(at))events.set(at,Array(9).fill(0));events.get(at)[j]+=v;};
  for(let j=0;j<8;j++){const a=ints[j];let lo=0,hi=a.length;while(lo<hi){const mid=(lo+hi)>>1;if(a[mid][1]<=start)lo=mid+1;else hi=mid;}for(let k=lo;k<a.length;k++){const [s,e,w]=a[k];if(s>=t)break;if(s<=start&&e>start)current[j]+=w;add(s,j,w);add(e,j,-w);}}
  p.set(proxy(current));for(const [at,d]of [...events].sort((a,b)=>a[0]-b[0])){p.advance(at-p.time);for(let j=0;j<9;j++)current[j]+=d[j];if(current.some(x=>x< -1e-7))throw Error('Invalid observed activity prefix');p.set(proxy(current));}p.advance(t-p.time);
 }
 state.publicObserver=p;const result=p.clone();result.set(Array(5).fill(0));return result;
}
module.exports={past};
