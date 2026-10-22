'use strict';
const C=require('./common.cjs'),{fs,path}=C,op=C.read(path.join(C.HERE,'OPERATION.json')),packet=C.read(C.packetPath),terminal=C.read(path.join(op.output,'TERMINAL.json'));
const rows=fs.readFileSync(path.join(op.output,'rows.jsonl'),'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse),main=rows.filter(r=>r.kind==='COMPARISON');
const inputs=C.read(path.join(C.HERE,'INPUTS.json')).inputs,all=[];
for(const spec of op.cases.filter(s=>s.kind==='COMPARISON')){
 const row=main.find(r=>r.id===spec.id);if(!row){all.push({id:spec.id,input:spec.input_id,model:spec.config.model,policy:spec.config.policy,status:'FAIL_OR_NOT_STARTED',n:spec.n,duration_s:spec.duration_s});continue;}
 const m=row.metrics,peers=main.filter(r=>r.metrics.input===m.input&&r.metrics.model===m.model),commonEnd=peers.some(r=>r.metrics.unfinished)?null:Math.max(...peers.map(r=>r.metrics.last_available_s)),input=inputs.find(s=>s.id===m.input),raw=C.read(row.raw_path),scenario={context:input.context};
 const classified=m.routes.classification_CPU+m.routes.classification_GPU+m.routes.classification_NPU;
 all.push({...m,status:'COMPLETE',common_policy_window_end_s:commonEnd,common_work_API_J:commonEnd===null?null:C.energy(packet,scenario,raw.simulation.activity,35,commonEnd),CPU_share:m.routes.classification_CPU/classified,GPU_share:m.routes.classification_GPU/classified,NPU_share:m.routes.classification_NPU/classified});
}
C.write(path.join(op.output,'SUMMARY.json'),{status:'DESCRIPTIVE_LONG_LOAD_NOT_PHYSICAL_VALIDATION',rows:all,terminal,new_RL:0,new_fit:0});
const headers=['input','n','duration_s','model','policy','status','on_time','planned','completed','unfinished','right_censored','U_on','U_planned','N_on','N_planned','P95_s','work_span_s','total_API_J','baseline_API_J','above_baseline_API_J','baseline_fraction','own_work_API_J','common_work_API_J','API_J_per_planned','AP_supply_mean','AP_supply_last60_mean','AP_peak','AP_outside_fit','max_ready','CPU_share','GPU_share','NPU_share'];
fs.writeFileSync(path.join(op.output,'SUMMARY.csv'),headers.join(',')+'\n'+all.map(r=>headers.map(h=>r[h]??'NA').join(',')).join('\n')+'\n');
const fmt=(n,d=2)=>Number.isFinite(n)?n.toFixed(d):'NA';
let text='# S26 작업량·공급 시간 확장 결과\n\n별도 새 seed/초기 이력0/MIX/3슬롯, 원 계수·납기·공통 배정기 고정. 독립 실기기 검증이 아니다. AP26~46.6℃ 밖 예측은 성과 채택에서 제외한다.\n\n';
text+='|입력|N/공급초|가정|정책|정시/전체|총API-J|기저%|초과API-J|작업창API-J|peak AP℃|NPU%|지원밖|\n|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|\n';
for(const r of all)text+=`|${r.input}|${r.n}/${r.duration_s}|${r.model}|${r.policy}|${r.status==='COMPLETE'?r.on_time+'/'+r.planned:r.status}|${fmt(r.total_API_J)}|${fmt(100*r.baseline_fraction)}|${fmt(r.above_baseline_API_J)}|${fmt(r.common_work_API_J)}|${fmt(r.AP_peak)}|${fmt(100*r.NPU_share)}|${r.status==='COMPLETE'?r.AP_outside_fit:'NA'}|\n`;
text+='\n작업창은 같은 입력/가정의 세 정책 중 마지막 AVAILABLE까지 공통창이며, 공급창/자기완료창/요청당 소비도 CSV에 보존한다. 실패/미완료는 표에서 제외하지 않았다. 기저는 각 시나리오의 고정 기저전력×전체 관측시간이고 초과분에는 활동 꼬리가 포함된다. 장시간과 미측정 조합의 가정 타당성은 별도 문제이며 NPU 분산이나 ATC 우위를 전제하지 않는다.\n\n'+JSON.stringify(terminal,null,2)+'\n';
fs.writeFileSync(path.join(op.output,'REPORT.md'),text);console.log(JSON.stringify({status:'REPORT_WRITTEN',comparison_rows:all.length,completed:main.length,failed:terminal.fail,path:path.join(op.output,'REPORT.md')}));
