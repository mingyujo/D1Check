'use strict';
const fs=require('node:fs'),path=require('node:path'),H=path.resolve(__dirname,'../S26-D1Check/s26_simulator/experiments/a24_policy_repair_v1');let src=fs.readFileSync(path.join(H,'report.cjs'),'utf8');
const extras=`
const decision=read(path.join(O,'NN_DECISION_DIAGNOSIS.json')),lookup=new Map(result.rows.map(r=>[r.label,r]));
const energyComponents=[.4,.65,.85,1.05].map(load=>{const rr=energy.rows.filter(r=>r.load===load&&r.variant==='REPAIR');return {load,rows:rr.length,mean_baseline_share_percent:avg(rr.map(r=>100*r.baseline_API_J/lookup.get(r.label).full_API_J)),component_mean_share_percent:Object.fromEntries(['CPU_wall_union','detection_CPU_increment','GPU_INFER','NPU_INFER','owner_union'].map(k=>[k,avg(rr.map(r=>100*r.channels_API_J[k]/lookup.get(r.label).full_API_J))])),conditional_fixed_recorded_work_bound_gap_percent:avg(rr.map(r=>r.conditional_fixedwork_upper_saving_percent))};});
const decisionSummary=[];for(const load of [.4,.65,.85,1.05])for(const variant of ['FROZEN','BASE','REPAIR']){const rr=decision.rows.filter(r=>r.kind==='EVAL'&&r.variant===variant&&r.load===load),count=sum(rr,r=>r.CPU_free_with_potentially_timely_normal_frames),hidden=sum(rr,r=>r.only_hidden_potentially_timely_normal_when_CPU_free);decisionSummary.push({load,variant,mean_session_forecast_queue_coverage:avg(rr.map(r=>r.mean_forecast_queue_coverage)),CPU_free_potential_normal_frames:count,only_hidden_normal_frames:hidden,hidden_fraction:count?hidden/count:null});}
`;
src=src.replace('const repair=evals.filter',extras+'\nconst repair=evals.filter').replace('all_repair_AVAILABLE:allCompleted','all_primary_EVAL_repair_AVAILABLE:allCompleted').replace('interpretation,physical_repairs:', 'interpretation,energy_components:energyComponents,decision_coverage:decisionSummary,physical_repairs:');
const additions=`
const energyTable=['## 에너지 성분과 후보 가시성 진단','', '|부하|REPAIR 기저 비중|CPU wall 합집합|탐지 CPU 증분|GPU INFER|NPU INFER|owner 합집합|고정한 관측작업 완화하한과 차이|','|---|---:|---:|---:|---:|---:|---:|---:|'];
for(const e of energyComponents)energyTable.push('|'+100*e.load+'%|'+fmt(e.mean_baseline_share_percent)+'%|'+['CPU_wall_union','detection_CPU_increment','GPU_INFER','NPU_INFER','owner_union'].map(k=>fmt(e.component_mean_share_percent[k])+'%').join('|')+'|'+fmt(e.conditional_fixed_recorded_work_bound_gap_percent)+'%|');
energyTable.push('','22개 양의전력basis를독립적분해각성분합이총API-J와맞는지확인했다. 마지막열은같은CPU grant/경로별INFER시간을고정한조건부완화하한과현재소비차이다. 그차이가달성가능한절감률이거나실제기기의전역최적여유라는뜻은아니다. 경로/온도에따른작업시간이바뀌면하한의전제도달라진다.','','|부하|방식|세션평균 예측 대기열 포함률|CPU여유·낙관적 일반납기 가능 frame|그중 후보밖에만 있는 frame|','|---|---|---:|---:|---:|');
for(const d of decisionSummary)energyTable.push('|'+100*d.load+'%|'+d.variant+'|'+fmt(100*d.mean_session_forecast_queue_coverage)+'%|'+d.CPU_free_potential_normal_frames+'|'+d.only_hidden_normal_frames+'|');
energyTable.push('','예측포함비율은지금즉시물리적으로실행가능한행동의비율과다르다. CPU가막혀있으면탐지일반은어느방식에서도그순간고를수없다. 오른쪽은CPU가빈경우만확인했고낙관적C0의단독탐지0.226초를썼으므로확정적납기가능성/인과효과의증거는아니다. 상태분포도정책에따라달라진다.','');
lines.splice(lines.indexOf('## 에너지·온도 모형 자체의 두 보완 검증'),0,...energyTable);
`;
src=src.replace('const report=path.join(R,',additions+'\nconst report=path.join(R,');fs.writeFileSync(path.join(H,'report.cjs'),src);console.log('COMPREHENSIVE_REPORT_COMPONENTS_AND_ACTIONABLE_COVERAGE_PREPARED');
