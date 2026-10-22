'use strict';
// Independent saved-only eligibility check. Does not import Python policy or engine.
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto');
const H=__dirname,R=path.resolve(H,'../../..'),A=path.join(R,'a24_simulator');
const O=path.join(A,'results/A24_IDLE_WAIT_REPAIR_20261019_01'),P=path.join(A,'results/A24_ATC_BC600_20261019_01');
const read=p=>JSON.parse(p.endsWith('.gz')?zlib.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0,removed=0;
function ok(x,message){checks++;if(!x)throw Error(message);}
function vector(f){
 if(f.comparison_complete!==true||f.capped!==false||f.no_future_arrivals!==true||f.no_future_latents!==true)return null;
 const v=[...f.cost,f.AP_end,f.peak];
 return v.length===7&&v.every(Number.isFinite)&&Number.isFinite(f.H_s)&&Array.isArray(f.visible_ids)?v:null;
}
const rows=read(path.join(P,'RESULT.json')).rows,replays=read(path.join(O,'DECISION_REPLAY.json.gz'));
const byCase=new Map();
for(const row of rows){
 const file=path.join(R,row.raw.path);ok(sha(file)===row.raw.sha256,'Original saved raw hash');
 byCase.set(row.case,read(file));
}
for(const row of replays){
 const raw=byCase.get(row.case),i=row.decision_index,c=raw.calls[i],s=raw.result.decisions[i].public_state;
 const expected=c.mask.slice(),metrics=c.forecasts.map(vector);
 ok(c.chosen===row.old_chosen&&s.now_ns===row.time_ns,'Original decision identity');
 if(!s.owners.length&&s.queue.length){
  const ids=new Set(s.queue.map(q=>q.request_id));
  for(let w=0;w<c.actions.length;w++)if(c.mask[w]&&c.actions[w].kind==='WAIT'&&metrics[w]){
   for(let d=0;d<c.actions.length;d++){
    const dispatch=c.actions[d],fd=c.forecasts[d],fw=c.forecasts[w];
    if(!c.mask[d]||dispatch.kind!=='DISPATCH'||!ids.has(dispatch.request_id)||!['CPU','GPU'].includes(dispatch.route)||!metrics[d])continue;
    if(Math.abs(fd.H_s-fw.H_s)>1e-8||JSON.stringify(fd.visible_ids.slice().sort())!==JSON.stringify(fw.visible_ids.slice().sort())||!fd.visible_ids.includes(dispatch.request_id))continue;
    let worse=false,strict=false;
    for(let k=0;k<7;k++){
     const x=metrics[d][k],y=metrics[w][k],t=1e-9+1e-9*Math.max(Math.abs(x),Math.abs(y));
     if(x-y>t)worse=true;
     if(y-x>t)strict=true;
    }
    if(!worse&&strict){expected[w]=false;removed++;break;}
   }
  }
 }
 ok(expected.every((v,j)=>v===row.mask[j]),'Independent Pareto eligibility mask');
 ok(expected.some(Boolean)&&expected[row.new_chosen],'Chosen action is eligible');
 if(s.owners.length)ok(row.new_chosen===row.old_chosen,'Active-state choice unchanged');
 for(let j=0;j<c.actions.length;j++)if(!row.mask[j]&&c.mask[j])ok(c.actions[j].kind==='WAIT','Only WAIT can be removed');
 if(row.old_chosen!==row.new_chosen)ok(row.guard.applied,'Choice changes require a filtered context');
}
ok(replays.length===3781&&removed===48,'Full saved-state coverage');
const report={status:'PASS',utc:new Date().toISOString(),frames:replays.length,checks,removed_WAIT_actions:removed,new_environment:0,new_fit:0,
 source_sha256:sha(__filename),replay_sha256:sha(path.join(O,'DECISION_REPLAY.json.gz'))};
fs.writeFileSync(path.join(O,'MASK_AUDIT.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
console.log('IDLE_WAIT_INDEPENDENT_MASK_PASS',checks,'checks',removed,'WAIT actions');
