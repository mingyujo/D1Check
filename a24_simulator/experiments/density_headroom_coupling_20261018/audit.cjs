'use strict';
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto'),phase=require('./phase.cjs'),allDeadline=require('./all_deadline.cjs');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(String(p).endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const same=require('node:util').isDeepStrictEqual;
let checks=0,worst=0;const need=(v,s)=>{checks++;if(!v)throw Error(s);},close=(a,b,s,tol=3e-6)=>{worst=Math.max(worst,Math.abs(a-b));need(Number.isFinite(a+b)&&Math.abs(a-b)<=tol,s+' '+Math.abs(a-b));};
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),parent=path.join(root,op.parent_output);
for(const p of [...op.sources,...op.input_pins])need(sha(p.path)===p.sha256,'Source/input pin');
const result=read(path.join(out,'RESULT.json')),terminal=read(path.join(out,'COMPLETE.json')),data=read(path.join(out,'EVALUATION.json')),old=read(path.join(parent,'EVALUATION.json')),parentAudit=read(path.join(parent,'AUDIT.json'));
need(parentAudit.status==='PASS'&&parentAudit.evaluation_sha256===sha(path.join(parent,'EVALUATION.json')),'Original independent physical audit binding');
need(terminal.result_sha256===sha(path.join(out,'RESULT.json'))&&result.evaluation_sha256===sha(path.join(out,'EVALUATION.json')),'Saved result binding');
need(result.LP_solves===40&&result.new_environment_START===0&&result.frozen_bank_restores===0&&result.new_physical_fit===0&&result.new_training===0,'No new native/fitting/training');
need(same(data.rows,old.rows)&&data.rows.length===112,'Preserve every original row and clock');
const model=read(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')),solo=Object.fromEntries(model.supported_states.map((s,i)=>[s,model.coefficients_W_proxy[i]]));
const H=solo.classification_GPU+solo.detection_CPU-solo['classification_GPU+detection_CPU'];delete solo['classification_GPU+detection_CPU'];solo.detection_GPU=.6013808404579677;
const proofs=read(path.join(out,'PHASE_PROOFS.json')).rows;
const capacityRows=[];
for(const pr of proofs){
 const jobs=read(path.join(parent,pr.case+'.BANK.json.gz')).jobs,ind=phase.derive(jobs,op.physics,solo,H,op.original_thermal_upper_c);
 for(const key of ['upper','original_upper','eta','crossing_temperature','convolution_burst_c','map_at_crossing'])if(key in pr||key in ind)close(pr[key],ind[key],'Independent phase scalar '+key,1e-10);
 for(const r of ['CPU','GPU'])for(const key of ['A','rho','burst','delta','derivative_upper'])close(pr.routes[r][key],ind.routes[r][key],'Independent phase proof '+r+key,1e-10);
 need(pr.upper<=pr.original_upper&&pr.upper>=op.physics.idle_c,'Same-model strengthened upper');
 for(const r of data.rows.filter(r=>r.case===pr.case))need(r.original.peak_AP_c<=pr.upper+1e-7,'Phase bound includes observed peak '+r.label);
 const cap=allDeadline.capacity(jobs);capacityRows.push({case:pr.case,...cap});
 for(const r of data.rows.filter(r=>r.case===pr.case))need(r.n-r.original.on_time>=cap.minimum_non_on_time_proved,'Capacity proof includes observed on-time counts');
}
let certs=0;
for(const b of data.bounds){
 const file=path.join(out,b.certificate);need(sha(file)===b.certificate_sha256,'Saved certificate SHA');
 const cert=read(file),p=cert.problem,n=p.cost.length,residual=[...p.cost];let dual=0;
 for(const [rows,rhs,lambda,ineq] of [[p.equal_rows,p.equal_rhs,p.equal_dual,false],[p.inequality_rows,p.inequality_rhs,p.inequality_dual,true]]){
  need(rows.length===rhs.length&&rhs.length===lambda.length,'Dual dimensions');
  for(let i=0;i<rows.length;i++){need(Number.isFinite(lambda[i])&&(!ineq||lambda[i]<=0),'Legal multiplier');dual+=rhs[i]*lambda[i];for(const [j,a] of rows[i])residual[j]-=a*lambda[i];}
 }
 for(let j=0;j<n;j++){need(Number.isFinite(p.lower[j])&&Number.isFinite(p.upper[j])&&p.upper[j]>=p.lower[j],'Finite variable box');dual+=residual[j]*(residual[j]>=0?p.lower[j]:p.upper[j]);}
 close(dual,p.repaired_dual,'Independent repaired dual');need(p.numerical_margin>=1e-4,'Conservative numeric margin');
 close(dual-p.numerical_margin+cert.constant_offset,b.new_coupled_lower,'Coupled lower');
 const previous=old.bounds.find(x=>x.case===b.case&&x.tier===b.tier&&x.kind===b.kind);need(!!previous,'Matching old bound');
 close(previous.lower,b.old_lower,'Old lower preserved',0);close(b.lower,Math.max(b.old_lower,b.new_coupled_lower),'Use strongest valid lower',0);
 need(b.old_certificate_sha256===previous.certificate_sha256&&b.new_status===p.status,'Old/new solve status and SHA preserved');
 close(b.maximum_reduction,b.kind==='energy'?100*(1-b.lower/b.reference_EDF):b.reference_EDF-b.lower,'Savings upper');
 for(const r of data.rows.filter(r=>r.case===b.case&&r.source!=='P0'&&r.completion&&r.original.incomplete===0&&r.original.response_missing===0&&Object.entries(b.targets).every(([k,v])=>r.original[k]>=v)&&(b.kind==='energy'||r.same_work_common_eligible))){
  need(b.lower<=(b.kind==='energy'?r.completion.total_J_proxy:r.common.mean_AP_c)+1e-5,'Bound includes found eligible schedule '+r.label);
 }
 certs++;
}
need(certs===40&&proofs.length===10,'Exact finite saved scope');
fs.writeFileSync(path.join(out,'ALL_DEADLINE_CAPACITY.json'),JSON.stringify({rows:capacityRows,new_environment_START:0,new_LP_solves:0},null,2)+'\n',{flag:'wx'});
fs.writeFileSync(path.join(out,'AUDIT.json'),JSON.stringify({status:'PASS',checks,max_absolute_error:worst,LP_certificates:certs,phase_proofs:proofs.length,
 parent_physical_audit_sha256:sha(path.join(parent,'AUDIT.json')),evaluation_sha256:sha(path.join(out,'EVALUATION.json')),result_sha256:sha(path.join(out,'RESULT.json')),
 all_original_rows:112,removed_rows:0,new_environment_START:0,new_LP_solves:0,utc:new Date().toISOString()},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:'PASS',checks,certs,worst}));
