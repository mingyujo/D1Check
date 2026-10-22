'use strict';
// Exact exponential past-state sufficient statistics; no new plant coefficients.
const math=require('./dynamic_cost_math_v2.cjs');
const cache=new WeakMap();
function pastState(obs,packet){
 let c=cache.get(obs);if(c)return c;
 const past=obs.cost_state.activity9.intervals,targets=obs.cost_state.targets,anchor=targets.AP.anchor,a=anchor.time_s??anchor.t_s;
 const state=new Map,anchorState=new Map;
 for(const beta of [.06,1/60,1,.1]){state.set(beta,math.stateSeries(past,[obs.time],beta,-30)[0]);anchorState.set(beta,math.stateSeries(past,[a],beta,-30)[0]);}
 const anchored=math.predict(packet.AP,{history_start_s:-30,activity9:{intervals:past},targets},[obs.sensor.time])[0];
 c={state,anchorState,anchor,a,targets,offset:obs.sensor.AP-anchored,
  boxPast:past.map(xs=>xs.filter(x=>x[1]>obs.time-.5).map(([l,r,w])=>[Math.max(l,obs.time-.5),Math.min(r,obs.time),w]))};
 cache.set(obs,c);return c;
}
function predictions(obs,packet,future,ts){
 const c=pastState(obs,packet),futureState=new Map;
 for(const beta of [.06,1/60,1,.1])futureState.set(beta,math.stateSeries(future,ts,beta,obs.time));
 const total=(beta,i)=>futureState.get(beta)[i].map((v,j)=>v+c.state.get(beta)[j]*Math.exp(-beta*(ts[i]-obs.time)));
 const hist=[c.anchor.AP_c??c.anchor.AP,c.anchor.SKIN_c??c.anchor.SKIN,c.anchor.BAT_c??c.anchor.BAT,c.anchor.pre20_AP_slope_c_s??c.anchor.pre20_AP_slope];
 const dot=(m,x)=>x.reduce((s,v,j)=>s+(v-m.mean[j])/m.scale[j]*m.coef[j],0);
 const ap=ts.map((t,i)=>{const f=[];for(const beta of [.06,1/60])f.push(...total(beta,i).map((v,j)=>v-c.anchorState.get(beta)[j]));for(const tau of [20,120])f.push(...[1,...hist].map(v=>v*-Math.expm1(-(t-c.a)/tau)));return (c.anchor.AP_c??c.anchor.AP)+dot(packet.AP,f)});
 if(packet.power.mode!=='POSITIVE_ADDITIVE')throw Error('Only registered positive additive power ABI');
 const all=[...new Set([...ts,...ts.map(t=>t-.5)])].sort((a,b)=>a-b),combined=future.map((xs,j)=>c.boxPast[j].concat(xs)),cum=math.integralSeries(combined,all,obs.time-.5),by=new Map(all.map((t,i)=>[t,cum[i]]));
 const pw=ts.map((t,i)=>{const box=by.get(t).map((v,j)=>(v-by.get(t-.5)[j])/.5),f=[1,c.targets.POWER_API.baseline.median_api_w,...box];for(const beta of [1,.1,1/60])f.push(...total(beta,i));return dot(packet.power,f)});
 return {ap,pw,offset:c.offset};
}
function evaluate(obs,packet,roll,model){
 if(!roll.activity)throw Error('Registered nominal activity required');
 const end=obs.horizon_s??180,times=new Set([obs.time,end]);
 for(let t=obs.time;t<end;){const age=t-obs.time;t=Math.min(end,t+(age<2?.05:age<15?.25:age<60?1:5));times.add(t)}
 for(const p of roll.plans)for(const t of [p.start,p.infer_start,p.infer_end,p.end])for(const shift of [0,.5])if(t+shift>=obs.time&&t+shift<=end)times.add(t+shift);
 const ts=[...times].sort((a,b)=>a-b),{ap,pw,offset}=predictions(obs,packet,roll.activity,ts);let J=0,H=0;
 for(let i=1;i<ts.length;i++){const dt=ts[i]-ts[i-1];J+=dt*(pw[i]+pw[i-1])/2;H+=dt*(ap[i]+ap[i-1])/2;}
 H+=offset*(end-obs.time);
 return {J,AP_area:H,peak:Math.max(...ap)+offset,misses:roll.misses,max_lateness:roll.max_lateness,forecast_nodes:roll.plans.length,grid_points:ts.length,plans:roll.plans,responses:roll.responses};
}
module.exports={rollout:require('./nominal_rollout.cjs').rollout,evaluate,predictions};
