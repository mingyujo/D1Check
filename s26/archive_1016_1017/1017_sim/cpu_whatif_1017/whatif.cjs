'use strict';
const fs=require('fs'),zlib=require('zlib'),path=require('path');
const R=process.env.S26SIM||'s26_simulator';
const {Simulator}=require(R+'/src/s26_simulator_v2.cjs');
const nomMod=require(R+'/src/rolling_action_v2.cjs');
const base=JSON.parse(zlib.gunzipSync(fs.readFileSync(R+'/data/engine_packet.json.gz')));
const lab=base.timing.spec.labels;
const idx=s=>lab.findIndex(l=>l.startsWith(s));
const variants={
 base:{},
 cpuCls_x0_3:{classification_CPU:0.3},
 cpuCls_x0_3_det_x0_35:{classification_CPU:0.3,detection_CPU:0.35},
 cpuCls_x0_05:{classification_CPU:0.05},
};
const scen=process.argv[2]||'R1-4-M128_BASE';
for(const [name,mods] of Object.entries(variants)){
  const p={...base,templates:base.templates.map(t=>mods[t.route]?{...t,inference_s:t.inference_s*mods[t.route]}:t)};
  const sc=p.scenarios.find(s=>s.id===scen);
  const nom=nomMod.publicNominals(p,sc);
  const prox=Object.fromEntries(Object.entries(nom.routes).map(([r,x])=>[r,[+(x.nominal_occupied_s*1000).toFixed(1),+x.incremental_J_proxy.toFixed(3),+x.AP_area_proxy.toFixed(2)]]));
  for(const pol of ['ROLLING_ATC_ROUTE_V2']){
   const cfg={identity:'WHATIF',phase:'RESOURCE_DYNAMIC',scenario:scen,policy:pol,stream:260016200,dt_s:0.005,power_dt_s:0.025,cost_model:'FULL',timing_variant:'CENTRAL',action_options:{classification_routes:['classification_CPU','classification_GPU','classification_NPU'],allow_wait:false,wait_step_s:0.05,wait_cap_s:2}};
   const r=new Simulator(p,sc,cfg).run();
   console.log(scen,name,JSON.stringify(prox),'on_time',r.service.all.on_time,'J',r.J_API0_180.toFixed(1),'routes',JSON.stringify(r.policy_route_counts));
  }
}
