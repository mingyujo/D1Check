'use strict';
// Private plant numerical step: sampled state is never exposed to the policy.
// All rates use the same midpoint AP and fixed within-step active peer set.
function integrate(dtCap,entries,APAt,rate){let dt=dtCap;if(entries.length){for(const e of entries){const rem=1-e.progress;if(dt*rate(e,APAt(dt/2))>=rem){let lo=0,hi=dt;for(let k=0;k<48;k++){const mid=(lo+hi)/2;if(mid*rate(e,APAt(mid/2))>=rem)hi=mid;else lo=mid}dt=(lo+hi)/2}}}const AP=entries.length?APAt(dt/2):null;return {dt,AP,rates:new Map(entries.map(e=>[e,rate(e,AP)]))}}
module.exports={integrate};
