'use strict';
const assert=require('assert/strict');
function expected(v){const [a,c,b,p]=v;return [a,c,b,p,Math.max(0,c+b-a),p,Math.max(0,a+p-c),Math.max(0,c+p-a)];}
exports.verify=function({read,need,close,reg,O,path}){
 const models=read(path.join(O,'NUMERICAL_PREFLIGHT_02/FOUR_ROUTE_MODELS.json')),op=read(reg.parent_operation_pin.path),old=read(op.thermal_models_pin.path).final_models.combined;
 const m=models.thermal;need(m.original_model_sha256===old.model_sha256,'Thermal original model binding');need(m.model_sha256===reg.expected_four_route_AP_sha256,'Four-route AP seal');
 need(m.coefficients.length===m.domains.length*11,'Extended eight-state feature width');
 for(let i=0;i<m.domains.length;i++){const b=old.coefficients.slice(i*7,(i+1)*7),want=[...b.slice(0,3),...expected(b.slice(3))];for(let j=0;j<11;j++)close(m.coefficients[i*11+j],want[j],'Independent coefficient transfer '+i+'/'+j);}
 const oldProfile=read(op.historical_profile_pin.path),keys=['classification_CPU','detection_CPU','classification_GPU','classification_GPU+detection_CPU','detection_GPU','classification_CPU+detection_GPU','classification_CPU+classification_GPU','detection_CPU+detection_GPU'];
 const v=expected(keys.slice(0,4).map(k=>oldProfile.cost_anchor.energy_increment_w[k]));for(let i=0;i<8;i++)close(models.profile.cost_anchor.energy_increment_w[keys[i]],v[i],'Independent power proxy transfer '+keys[i]);
 need(models.timing.model_digest===reg.expected_four_route_timing_digest,'Four-route timing seal');need(models.ratios.length===8,'8 historical ratios from two roles');
 const evidence=read(reg.input_pins.find(p=>path.basename(p.path)==='DG_TIMING_EVIDENCE.json').path);
 // Evidence also has a direct exact local byte copy among current input pins.
 for(const r of models.ratios){const g=evidence.rows.find(x=>x.source_request_id===r.GPU_source_id),c=evidence.rows.find(x=>x.source_request_id===r.CPU_source_id);need(!!g&&!!c,'Historical pair exists');need(g.role===c.role&&g.ordinal===c.ordinal&&g.gpu_delegate_verified,'Historical matched ratio provenance');for(let j=0;j<5;j++)close(r.stages_ratio[j],g.durations_ns[j]/c.durations_ns[j],'Historical stage ratio');}
};
exports.verifyRaw=function({read,need,close,raw,r,O,path}){
 need(JSON.stringify(r.legal_route_scope)===JSON.stringify({C:['CPU','GPU'],D:['CPU','GPU']}),'Both task route scopes');
 const q=raw.prediction.requests;for(const row of q){if(row.dispatch_ns===null)continue;const routeKey=row.task+'_'+row.route;need(routeKey in r.route_counts,'Only four route keys');
  need(row.dispatch_ns>=row.queue_entry_ns&&row.queue_entry_ns>=row.scheduled_arrival_ns,'Admission clock order');
  const times=['execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns'].map(k=>row[k]);
  need(times.every((v,i)=>v===null||i===0||times[i-1]===null||v>=times[i-1]),'Five phase order');need(row.response_ns===row[row.task==='C'?'output_ready_ns':'persist_complete_ns'],'Task response boundary');
  if(row.task==='D'&&row.route==='GPU'){
   const t=row.timing.DG_transfer;need(!!t&&!t.current_GPU_observation,'DG result explicitly projected');
   for(let i=0;i<5;i++)close(row.timing.stages_ns[i],t.base_serial_vector_ns[i]*t.historical_ratio.stages_ratio[i],'DG stage-ratio prediction rounding',.50001);
  }
 }
 for(const task of ['C','D'])for(const route of ['CPU','GPU'])need(r.route_counts[task+'_'+route]===q.filter(x=>x.task===task&&x.route===route).length,'Actual placement census');
 if(r.policy.startsWith('ROLLING_ATC_RL'))need(r.D_GPU_legal_action_slots>0,'Actual NN bank exposes DG actions');
};
