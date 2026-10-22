'use strict';
// Independent saved-source arithmetic. Does not import the Python analyzer or simulator.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const R=path.resolve(__dirname,'../../..'),A=path.join(R,'a24_simulator'),O=path.join(A,'results/A24_S26_SENSITIVITY_20261022_01'),H=path.join(A,'experiments/a24_s26_sensitivity_20261022');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');let checks=0,maxerr=0;
function ok(v,m){checks++;if(!v)throw Error(m);}
function near(a,b){if(a===null||b===null){ok(a===b,'Null equal');return;}maxerr=Math.max(maxerr,Math.abs(a-b));ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<3e-7,'Numeric '+a+' / '+b);}
const mean=v=>v.reduce((a,b)=>a+b,0)/v.length,ps=['FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_RISK','BC_NEURAL_URGENT'],bc=ps[4],reg=read(path.join(H,'OPERATION.json')),raw=[];
for(const p of reg.source_pins)ok(sha(path.join(R,p.path))===p.sha256,'Source '+p.path);
for(const source of ['A24_S26_SCALE_20261022_01','A24_S26_JOINT_20261022_01']){
 const root=path.join(A,'results',source),data=read(path.join(root,'RESULT.json')),audit=read(path.join(root,'AUDIT_JS.json'));ok(audit.status==='PASS','Parent physics audit');const derived=new Map(audit.derived.map(r=>[r.label,r]));
 for(const r of data.rows){const c=r.condition,m=r.metrics,d=derived.get(r.label),v={source,label:r.label,setting:c.setting,role:c.role,n:c.n,burst:c.burst,load:c.nominal_load,mix:c.mix,draw:c.draw,policy:r.policy,J:m.J,AP:m.AP,J_no_pre35:m.J-m.pre35_baseline_J,J_supply:d.supply_J,J_own_completion:d.own_completion_J};
  for(const g of ['ALL','U','N']){for(const k of ['n','on','missing','incomplete','P95'])v[g+'_'+k]=m.service[g][k];v[g+'_on_pct']=100*m.service[g].on/m.service[g].n;}
  v.J_per_request=m.J/m.service.ALL.n;v.J_per_ontime=m.J/m.service.ALL.on;raw.push(v);
 }
}
ok(raw.length===160,'160 sources');const bylabel=new Map(raw.map(r=>[r.label,r]));ok(bylabel.size===160,'Unique label');const produced=read(path.join(O,'EPISODES.json'));ok(produced.length===160,'160 export');
for(const r of produced){const a=bylabel.get(r.label);ok(a&&r.policy===a.policy&&r.setting===a.setting,'Binding');for(const k of Object.keys(a)){if(typeof a[k]==='number')near(r[k],a[k]);}}
function agg(rr){
 const out={};for(const k of ['J','AP','J_no_pre35','J_supply','J_own_completion'])out[k]=rr.every(r=>r[k]!==null)?mean(rr.map(r=>r[k])):null;
 for(const g of ['ALL','U','N']){for(const k of ['n','on','missing','incomplete'])out[g+'_'+k]=rr.reduce((a,r)=>a+r[g+'_'+k],0);out[g+'_on_pct']=100*out[g+'_on']/out[g+'_n'];out[g+'_P95']=mean(rr.map(r=>r[g+'_P95']));}
 out.J_per_request=rr.reduce((s,r)=>s+r.J,0)/out.ALL_n;out.J_per_ontime=rr.reduce((s,r)=>s+r.J,0)/out.ALL_on;return out;
}
function comparison(b,a){return {ALL_gain_pp:b.ALL_on_pct-a.ALL_on_pct,energy_saving_pct:100*(a.J-b.J)/a.J,AP_reduction_C:a.AP-b.AP};}
function checkCell(cell,rr){
 const computed={};for(const p of ps){const q=rr.filter(r=>r.policy===p);ok(q.length>0,'Each policy');computed[p]=agg(q);for(const k of Object.keys(computed[p]))near(cell.policies[p][k],computed[p][k]);}
 let joint=true,mixed=true,quality=true;
 for(const p of ps.slice(0,4)){const c=comparison(computed[bc],computed[p]);for(const k of Object.keys(c))near(cell.comparisons[p][k],c[k]);if(ps.indexOf(p)<3)joint=joint&&c.ALL_gain_pp>1e-9&&c.energy_saving_pct>1e-9&&c.AP_reduction_C>1e-9;}
 for(const m of cell.mixes){
  const per={};for(const p of ps){per[p]=agg(rr.filter(r=>r.policy===p&&r.mix===m.mix));for(const k of Object.keys(per[p]))near(m.policies[p][k],per[p][k]);}
  for(const p of ps.slice(0,4)){const c=comparison(per[bc],per[p]);for(const k of Object.keys(c))near(m.comparisons[p][k],c[k]);if(ps.indexOf(p)<3)mixed=mixed&&c.ALL_gain_pp>=-1e-9&&c.energy_saving_pct>1e-9&&c.AP_reduction_C>1e-9;}
  const b=per[bc];quality=quality&&b.ALL_on_pct>=95&&b.U_on_pct>=99&&b.ALL_missing===0&&b.ALL_incomplete===0;
 }
 ok(joint===cell.aggregate_joint,'Aggregate joint');ok(mixed===cell.mixed_nonworse_joint,'Mixture guard');ok(quality===cell.quality_gate,'Quality guard');
}
const cells=read(path.join(O,'CELLS.json'));ok(cells.length===13,'13 phase settings');for(const c of cells)checkCell(c,raw.filter(r=>r.setting===c.setting&&r.role===c.role));
const draws=read(path.join(O,'DRAW_STABILITY.json'));ok(draws.length===16,'16 setting draw groups');for(const c of draws)checkCell(c,raw.filter(r=>r.setting===c.setting&&r.role===c.role&&r.draw===c.draw));
const dev=raw.filter(r=>r.role==='DEV'),met=['ALL_on_pct','U_on_pct','N_on_pct','AP','J_per_request','J_per_ontime','EDF_ALL_gain_pp','EDF_energy_saving_pct','EDF_AP_reduction_C'];
function value(r,k){if(!k.startsWith('EDF_'))return r[k];const a=dev.find(a=>a.n===r.n&&a.burst===r.burst&&a.load===r.load&&a.mix===r.mix&&a.policy==='EDF_DYN');return k==='EDF_ALL_gain_pp'?r.ALL_on_pct-a.ALL_on_pct:k==='EDF_energy_saving_pct'?100*(1-r.J/a.J):a.AP-r.AP;}
const f=read(path.join(O,'FACTORS.json'));ok(f.contrasts.length===120&&f.summary.length===15,'Factor count');
for(const c of f.contrasts){const a=bylabel.get(c.low),b=bylabel.get(c.high),axis={N:'n',BURST:'burst',LOAD:'load'}[c.factor];ok(a.role===b.role&&a.role==='DEV'&&a.policy===b.policy&&a.mix===b.mix,'Matched phase/policy/mix');for(const k of ['n','burst','load'])ok(k===axis?b[k]===2*a[k]:b[k]===a[k],'Only one scale factor');for(const k of met)near(c.delta[k],value(b,k)-value(a,k));}
for(const s of f.summary){const rr=f.contrasts.filter(c=>c.factor===s.factor&&c.policy===s.policy);ok(rr.length===s.pairs&&rr.length===8,'Eight pairs per policy/factor');for(const k of met){const vals=rr.map(r=>r.delta[k]),stat=s.metrics[k];near(stat.signed_mean,mean(vals));near(stat.mean_abs,mean(vals.map(Math.abs)));near(stat.min,Math.min(...vals));near(stat.max,Math.max(...vals));}}
const interactions=read(path.join(O,'INTERACTIONS.json'));ok(interactions.length===60,'DID count');for(const c of interactions){const q=Object.fromEntries(Object.entries(c.labels).map(([k,v])=>[k,bylabel.get(v)]));for(const k of met)near(c.DID[k],value(q['11'],k)-value(q['10'],k)-value(q['01'],k)+value(q['00'],k));}
const wts=read(path.join(O,'ANALYTIC_WEIGHTING.json'));ok(wts.length===606,'Weight grid count');for(const r of wts){const c=cells.find(c=>c.role==='CONF'&&c.setting===r.setting),m50=c.mixes.find(m=>m.mix===.5),m75=c.mixes.find(m=>m.mix===.75),w=r.w_C50_scenario,b50=m50.policies[bc],b75=m75.policies[bc],a50=m50.policies[r.reference],a75=m75.policies[r.reference];near(r.ALL_gain_pp,w*(b50.ALL_on_pct-a50.ALL_on_pct)+(1-w)*(b75.ALL_on_pct-a75.ALL_on_pct));const a=w*a50.J+(1-w)*a75.J,b=w*b50.J+(1-w)*b75.J;near(r.energy_saving_pct,100*(a-b)/a);near(r.AP_reduction_C,w*(a50.AP-b50.AP)+(1-w)*(a75.AP-b75.AP));if(w===.5){for(const k of ['ALL_gain_pp','energy_saving_pct','AP_reduction_C'])near(r[k],c.comparisons[r.reference][k]);}}
const thresholds=read(path.join(O,'WEIGHT_THRESHOLDS.json'));ok(thresholds.length===6,'Threshold count');for(const t of thresholds){near(t.ALL_zero_w,-t.ALL_gain_at_w0_pp/(t.ALL_gain_at_w1_pp-t.ALL_gain_at_w0_pp));near(t.ALL_zero_w*t.ALL_gain_at_w1_pp+(1-t.ALL_zero_w)*t.ALL_gain_at_w0_pp,0);ok(t.ALL_gain_positive_for_w_above_root===true&&t.energy_and_AP_positive_at_both_endpoints===true,'Threshold direction/endpoint checks');}
const windows=read(path.join(O,'WINDOWS.json'));ok(windows.length===52,'Window comparisons');for(const w of windows){const c=cells.find(c=>c.role===w.role&&c.setting===w.setting),b=c.policies[bc],a=c.policies[w.reference];for(const k of ['J','J_no_pre35','J_supply','J_own_completion'])near(w[k+'_saving_pct'],b[k]===null||a[k]===null?null:100*(a[k]-b[k])/a[k]);}
const summary=read(path.join(O,'SUMMARY.json')),order=f.summary.filter(r=>r.policy===bc).sort((a,b)=>b.metrics.ALL_on_pct.mean_abs-a.metrics.ALL_on_pct.mean_abs).map(r=>r.factor);ok(JSON.stringify(order)===JSON.stringify(summary.BC_abs_ALL_effect_order),'Sensitivity order');ok(summary.new_environments===0&&summary.new_fits===0&&summary.new_measurements===0,'Saved only');
for(const p of reg.source_pins)ok(sha(path.join(R,p.path))===p.sha256,'Source remained frozen');
fs.writeFileSync(path.join(O,'AUDIT_JS.json'),JSON.stringify({status:'PASS',checks,max_abs_error:maxerr,source_episodes:160,matched_pairs:120,DID:60,weighted_points:606,new_environments:0,new_fits:0,independent_of_analyzer:true,physics_audits_reused_not_rerun:true,script_sha256:sha(__filename)},null,2),{flag:'wx'});console.log('SENSITIVITY_AUDIT_PASS',checks,maxerr,order.join('>'));
