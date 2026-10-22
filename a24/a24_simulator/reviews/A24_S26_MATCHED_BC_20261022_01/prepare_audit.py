from pathlib import Path
import hashlib,json
V=Path(__file__).resolve().parent;R=V.parents[2];source=V.parent/'A24_S26_SCALE_20261022_01/audit.cjs';target=V/'audit.cjs';assert not target.exists()
s=source.read_text(encoding='utf-8').replace('A24_S26_SCALE_20261022_01','A24_S26_MATCHED_BC_20261022_01').replace('experiments/a24_s26_scale_20261022','experiments/a24_s26_matched_bc_20261022').replace('starts.length<=120','starts.length<=105')
s=s.replace("const riskModel=read(path.join(A,'results/A24_NN_URGENT_TIE_20261021_01/RISK_CALIBRATION.json'));","const riskModel={task_margin_s:{C:0,D:0}};")
old="vm.runInContext(src.slice(src.indexOf('function dominance'),src.indexOf('const result=read'))+';globalThis.checkBank=auditBank;',sandbox);"
guard=r'''
 let riskAllowed=allowed,guardGate=idle.slice();
 if(c.deadline_wait_guard){
  const lookupQ=new Map(s.queue.map(q=>[q.request_id,q])),slack={},fastest={};
  for(let i=0;i<c.actions.length;i++){
   const a=c.actions[i];if(!idle[i]||a.kind!=='DISPATCH')continue;const q=lookupQ.get(a.request_id);if(q.priority!=='U')continue;
   const f=c.forecasts[i],end=f.responses_s[q.request_id]??f.H_s,v=q.deadline_ns/1e9-end-riskModel.task_margin_s[q.task];
   if(slack[q.request_id]===undefined||v>slack[q.request_id]){slack[q.request_id]=v;fastest[q.request_id]=i;}
  }
  const blocked=[],reasons=[];
  for(let i=0;i<c.actions.length;i++){
   const a=c.actions[i];if(!idle[i]||a.kind==='DISPATCH')continue;const w=(a.wait_ns??a.max_wait_ns??0)/1e9,critical=Object.keys(slack).filter(id=>slack[id]<=w+config.tick_s+1e-8);
   if(critical.length){guardGate[i]=false;blocked.push(i);reasons.push({index:i,wait_bound_s:w,critical_ready_urgent_ids:critical});}
  }
  ok(JSON.stringify(blocked)===JSON.stringify(c.deadline_wait_guard.blocked_wait_indices),'Independent deadline WAIT exclusions');
  ok(JSON.stringify(guardGate)===JSON.stringify(c.guard_mask),'Guard physical mask');
  ok(JSON.stringify(fastest)===JSON.stringify(c.deadline_wait_guard.fastest_dispatch_indices),'Fastest public dispatch candidate');
  for(const [id,v] of Object.entries(slack))near(v,c.deadline_wait_guard.urgent_slack_s[id],'Public urgent latest-start slack',1e-10);
  ok(JSON.stringify(reasons)===JSON.stringify(c.deadline_wait_guard.reasons),'WAIT bounds and causal critical IDs');
  near(c.deadline_wait_guard.tick_s,config.tick_s,'Guard tick',1e-12);ok(c.deadline_wait_guard.future_information===false,'No future guard input');
  riskAllowed=c.actions.map((_,i)=>i).filter(i=>guardGate[i]);ok(riskAllowed.length>0,'Guard retains action');
 }
'''
new="let bankCode=src.slice(src.indexOf('function dominance'),src.indexOf('const result=read'));\n"
new += 'bankCode=bankCode.replace(" const riskBest=allowed.map",'+json.dumps(guard)+'+" const riskBest=riskAllowed.map");\n'
new += 'bankCode=bankCode.replace("mask=idle.map((v,i)=>!!v&&i<riskPairs.length", "mask=guardGate.map((v,i)=>!!v&&i<riskPairs.length");\n'
new += "vm.runInContext(bankCode+';globalThis.checkBank=auditBank;',sandbox);"
assert old in s;s=s.replace(old,new)
old="sandbox.checkBank(s,c,bank,r.config,null,row.policy);policyChecks++;"
new="sandbox.riskModel={task_margin_s:d.risk};sandbox.checkBank(s,c,bank,r.config,null,row.policy.startsWith('TEACHER')?'TEACHER_RISK':row.policy);policyChecks++;"
assert old in s;s=s.replace(old,new)
# Separate-language residual calibration census, no fitting or policy rerun.
extra=r'''
const calibration=read(path.join(O,'RISK_CALIBRATION.json')),rv={C:[],D:[]};let ci=0;
for(const row of result.rows.filter(r=>r.kind==='TRAIN_CAL')){
 const d=read(path.join(R,row.raw.path)),qs=new Map(d.result.requests.map(q=>[q.request_id,q]));
 for(const c of d.calls){if(c.action.kind!=='DISPATCH')continue;const q=qs.get(c.action.request_id),p=c.forecasts[c.chosen].responses_s[q.request_id];if(q.response_ns===null||p===undefined)continue;
  const residual=q.response_ns/1e9-p,v=calibration.samples[ci++];ok(v.split==='TRAIN'&&v.case===row.case&&v.request_id===q.request_id&&v.raw_sha256===row.raw.sha256,'Calibration TRAIN binding');near(v.residual_s,residual,'TRAIN residual',1e-12);rv[q.task].push(residual);
 }
}
ok(ci===calibration.samples.length,'All calibration samples');for(const task of ['C','D']){rv[task].sort((a,b)=>a-b);ok(rv[task].length>=20,'Q90 minimum');near(calibration.task_margin_s[task],Math.max(0,rv[task][Math.ceil(.9*rv[task].length)-1]),'TRAIN q90',1e-12);}
const freeze=read(path.join(O,'FREEZE.json')),firstEval=Math.min(...events.filter(e=>e.event==='START'&&e.kind==='EVAL').map(e=>e.unix));ok(freeze.unix<firstEval&&freeze.fit_stage===2&&freeze.no_EVAL_selection,'Frozen stage2 before EVAL');
'''
pos="fs.writeFileSync(path.join(O,'AUDIT_JS.json')";assert pos in s;s=s.replace(pos,extra+'\n'+pos)
target.write_text(s,encoding='utf-8');(V/'AUDIT_PROVENANCE.json').write_text(json.dumps({'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'changes':'New namespace105 budget, per-row TRAIN risk, independently reconstructed public deadline WAIT gate, residual census and freeze ordering. Original physics/costs/baselines retained.'},ensure_ascii=False,indent=2),encoding='utf-8');print('MATCHED_AUDIT_PREPARED')
