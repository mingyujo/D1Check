// regime runner: synthetic request tables on sealed initial contexts; physics untouched
const fs=require('fs'),zlib=require('zlib'),path=require('path');
const [simdir,jobsf,outf]=process.argv.slice(2);
const {Simulator}=require(path.join(simdir,'src/s26_simulator_v2.cjs'));
const packet=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(simdir,'data/engine_packet.json.gz'))));
function makeRequests(w){ // w: {bursts, gap_s, cls, det, smooth, urgent_det}
  const per=w.cls+w.det,req=[];let ord=0;
  for(let b=0;b<w.bursts;b++){
    const types=[];for(let i=0;i<per;i++){types.push(i<w.cls?'classification':'detection');}
    // interleave like R21 (3 cls,1 det,3 cls,1 det)
    const detPos=new Set();for(let k=0;k<w.det;k++)detPos.add(Math.floor((k+1)*per/w.det)-1);
    const order=[];for(let i=0;i<per;i++)order.push(detPos.has(i)?'detection':'classification');
    order.forEach((t,i)=>{const off=35+(w.smooth?(b*per+i)*w.gap_s/per:b*w.gap_s);
      req.push({ordinal:ord++,offset_ns:Math.round(off*1e9),task_id:t,priority:t==='classification'?'urgent':'normal',deadline_ms:t==='classification'?800:2000});});
  }
  return req;
}
const orig=packet.timing.coef.slice();
function setK(k){packet.timing.coef=orig.map((c,j)=>packet.timing.spec.labels[j].startsWith('AP:')?c*k:c);}
const out=fs.openSync(outf,'a');
for(const j of JSON.parse(fs.readFileSync(jobsf))){
  setK(j.k??1);
  const base=packet.scenarios.find(s=>s.id===j.context);
  const sc={...base,id:'SYN|'+j.wid+'|'+j.context,requests:makeRequests(j.w),policy:j.policy,policy_args:null};
  const cfg={dt_s:.005,power_dt_s:.025,cost_model:'FULL',timing_variant:j.tv||'CENTRAL',policy:j.policy,stream:j.stream,
    action_options:{classification_routes:['classification_CPU','classification_GPU','classification_NPU'],allow_wait:true,wait_step_s:.05,wait_cap_s:2,...(j.action_options||{})}};
  let row;const t=Date.now();
  try{const r=new Simulator(packet,sc,cfg).run();
   row={id:j.id,k:j.k??1,wid:j.wid,context:j.context,policy:j.tag||j.policy,stream:j.stream,n:sc.requests.length,hard_feasible:r.hard_feasible,on_time:r.service.all.on_time,u_on:r.service.urgent.on_time,u_n:r.service.urgent.planned,n_on:r.service.normal.on_time,n_n:r.service.normal.planned,unfinished:r.unfinished,uP95:r.service.urgent.p95_s,J:r.J_API0_180,AP_mean:r.AP35_180_mean,AP_peak:r.AP_peak_sampled,AP180:r.AP180,censored:r.right_censored_at??null,wait_s:r.wait_s,routes:r.policy_route_counts??null,ms:Date.now()-t};
  }catch(e){row={id:j.id,wid:j.wid,policy:j.policy,error:String(e).slice(0,300)}}
  fs.writeSync(out,JSON.stringify(row)+'\n');
}
