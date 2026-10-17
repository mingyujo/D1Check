'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),data=read(path.join(out,'EVALUATION.json')),audit=read(path.join(out,'AUDIT.json'));
if(audit.evaluation_sha256!==sha(path.join(out,'EVALUATION.json')))throw Error('Audit binding');
const rows=data.rows,ids=[...new Set(rows.map(r=>r.case))],summaries=[],f=(x,n=3)=>x==null?'미정의':Number(x).toFixed(n);
for(const cid of ids){const local=rows.filter(r=>r.case===cid&&r.source!=='P0'),ref=local.find(r=>r.source==='ORIGINAL'&&r.policy==='EDF');
 for(const tier of ['EDF','STRONG']){
  const eb=data.bounds.find(b=>b.case===cid&&b.tier===tier&&b.kind==='energy'),tb=data.bounds.find(b=>b.case===cid&&b.tier===tier&&b.kind==='temperature');
  const legal=local.filter(r=>r.completion!==null&&r.original.incomplete===0&&r.original.response_missing===0&&Object.entries(eb.targets).every(([k,v])=>r.original[k]>=v));
  const common=legal.filter(r=>r.same_work_common_eligible),energy=legal.reduce((a,b)=>a.completion.total_J_proxy<b.completion.total_J_proxy?a:b),heat=common.reduce((a,b)=>a.common.mean_AP_c<b.common.mean_AP_c?a:b);
  const saving=r=>100*(1-r.completion.total_J_proxy/ref.completion.total_J_proxy),cooling=r=>ref.common.mean_AP_c-r.common.mean_AP_c;
  const joint=common.filter(r=>saving(r)>=10&&cooling(r)>=.5);
  summaries.push({case:cid,condition:ref.condition,tier,targets:eb.targets,reference_EDF_completion_J:ref.completion.total_J_proxy,
   reference_EDF_common_AP_c:ref.common.mean_AP_c,common_end_s:ref.common.end_ns/1e9,
   feasible_energy:energy.label,achieved_energy_saving_percent:saving(energy),feasible_heat:heat.label,achieved_temperature_reduction_c:cooling(heat),
   best_energy_temperature_reduction_c:energy.same_work_common_eligible?cooling(energy):null,
   best_heat_energy_saving_percent:saving(heat),maximum_energy_saving_percent:eb.maximum_reduction,maximum_temperature_reduction_c:tb.maximum_reduction,
   energy10_impossible_by_relaxation:eb.maximum_reduction<10,temperature_point5_impossible_by_relaxation:tb.maximum_reduction<.5,
   feasible_joint_targets:joint.map(r=>r.label),strict_numeric_relaxation:true,global_optimum_found:false});
 }
}
const aggregate=[];
for(const tier of ['EDF','STRONG'])for(const factor of [.5,1,1.5,2,3]){const g=summaries.filter(s=>s.tier===tier&&s.condition.rate_multiplier===factor),B=g.reduce((s,r)=>s+r.reference_EDF_completion_J,0);
 aggregate.push({tier,factor,achieved_energy_saving_percent:100*g.reduce((s,r)=>s+r.reference_EDF_completion_J*r.achieved_energy_saving_percent/100,0)/B,
   maximum_energy_saving_percent:100*g.reduce((s,r)=>s+r.reference_EDF_completion_J*r.maximum_energy_saving_percent/100,0)/B,
   achieved_temperature_reduction_c:g.reduce((s,r)=>s+r.achieved_temperature_reduction_c,0)/2,
   maximum_temperature_reduction_c:g.reduce((s,r)=>s+r.maximum_temperature_reduction_c,0)/2,
   feasible_choices_are_posthoc_per_case_portfolios:true});}
fs.writeFileSync(path.join(out,'HEADROOM_SUMMARY.json'),JSON.stringify({cases:summaries,aggregate,online_policy_claim:false},null,2)+'\n',{flag:'wx'});
const table=summaries.map(s=>`|${s.condition.rate_multiplier}|${s.condition.pattern}|${s.tier}|${s.targets.on_time}/${s.targets.urgent_on_time}|${f(s.achieved_energy_saving_percent)}|${f(s.maximum_energy_saving_percent)}|${f(s.achieved_temperature_reduction_c)}|${f(s.maximum_temperature_reduction_c)}|${s.feasible_joint_targets.length}|`).join('\n');
const exclusions=rows.map(r=>{
 const notes=[];if(r.source==='P0')notes.push('P0:원본 재현 검증용, 정책 우위 선정 대상에서만 제외');
 for(const tier of ['EDF','STRONG']){const target=data.bounds.find(b=>b.case===r.case&&b.tier===tier&&b.kind==='energy').targets,why=[];
  if(r.original.response_missing)why.push('미응답 '+r.original.response_missing);
  if(r.original.incomplete)why.push('미완료 '+r.original.incomplete);
  if(r.original.on_time<target.on_time)why.push('전체정시 '+r.original.on_time+'<'+target.on_time);
  if(r.original.urgent_on_time<target.urgent_on_time)why.push('긴급정시 '+r.original.urgent_on_time+'<'+target.urgent_on_time);
  notes.push(tier+':'+(why.length?'선정 제외('+why.join(', ')+')':'납기 적격'));
 }
 if(!r.same_work_common_eligible)notes.push('온도 선정 제외:동결 공통창 안에 전부 완료하지 못함');else notes.push('온도창 완료 적격');
 return {label:r.label,source:r.source,notes};
});
fs.writeFileSync(path.join(out,'ALL_ROWS_WITH_REASONS.json'),JSON.stringify({rows:rows.map((r,i)=>({...r,remarks:exclusions[i].notes})),all_rows_displayed:true,removed_rows:0},null,2)+'\n',{flag:'wx'});
const all=rows.map((r,i)=>`|${r.case}|${r.policy}|${r.source}|${r.original.on_time}/${r.n}|${r.original.urgent_on_time}/${r.original.urgent_planned}|${f(r.original.P95_completed_response_s)}|${r.original.response_missing}/${r.original.incomplete}|${f(r.completion?.duration_s)}|${f(r.completion?.total_J_proxy)}|${f(r.common.mean_AP_c)}|${f(r.original.peak_AP_c)}|${exclusions[i].notes.join('; ')}|`).join('\n');
const counts=Object.fromEntries(['EDF','STRONG'].map(t=>[t,{energy10_impossible:summaries.filter(s=>s.tier===t&&s.energy10_impossible_by_relaxation).length,temperature_point5_impossible:summaries.filter(s=>s.tier===t&&s.temperature_point5_impossible_by_relaxation).length,found_joint:summaries.filter(s=>s.tier===t&&s.feasible_joint_targets.length).length}]));
const report=`# 같은 A24 모형·밀도 입력의 열·에너지 절감 여지

2026-10-18 사용자 요청에 따라 원 LOAD_DENSITY의10입력·잠재작업량·물리계수·도착·납기·서비스/관측창을 고정했다. 새82실행(정확engine/model 재현2＋8종 오프라인 일정×10)과40 LP를 별도 등록했다. 학습·물리fit·실기기0이다. 원32/NN/실측을 수정하지 않았다.

![발견한 개선과 낙관적 상한](HEADROOM.png)

## 비교와 판정의 범위

- EDF층은 조건별 EDF의 전체/긴급 정시 수를 각각 보존한다. STRONG층은 EDF와 현재RL 중 더 큰 전체/긴급 정시 수를 각각 보존한다. 이는 모든요청이 정시라는 뜻이 아니다. 과부하에서 불가능할수있는 전요청정시로 바꿔말하지 않는다. 모든후보의 전체도착 분모·완료P95·미응답/미완료를 아래 공개한다.
- 에너지는 첫공급35초부터 자기 마지막AVAILABLE까지의 기저＋증분J*다. 전부완료하지않으면 미정의다. 평균온도는 원3정책의공통완료시각을 조건별로사전에동결한 창으로비교한다. 그시각까지전부완료한일정만 온도 적격이다. 더늦게처리해 차갑게보이는일정은 열우위로쓰지않는다. 열상한은 이같은완료시한을지키는문제의상한이며 전service창을허용한에너지상한과범위가다르다.
- CPU/GPU각1·최대2·AVAILABLE비선점·원명목긴급WAIT mask·총12초/선두1.5초·공통50ms모음을 유지했다. 후보8개 제한은정책제한이므로 오프라인진단에서는전체ready와 양route실현작업량을쓴다. 미래정보를아는 진단일정이며 온라인달성성/새RL우위/전역최적값을주장하지않는다.
- ENERGY/TOTAL/REGRET/LP_ROUTE/HEAT/COOL35/COOL36/SLA_ENERGY의8개 사전고정휴리스틱을 모두보고한다. 기준EDF/ATC/RL30저장일정도 그대로포함한다. 발견한최저에너지와최저온도는 서로다른일정일수있다. 공동10%/.5℃는 반드시 같은일정에서 확인한다. 조건별사후선택모음은 단일정책성능이아니다.
- 사용자 추가지시에 따라 신규82(재현2 포함)＋기준30의112행을 모두 표시하며 삭제0이다. 선정에서 제외되는 이유는 EDF/STRONG 납기와 온도창 완료 여부별로 비고에 적었다. P0도 표에 남긴다. 모든40 LP 상태/수치 여유는 CERT와 BOUNDS에 보존한다.
- LP는 연속route분할·독립온도별실행작업·가장유리한구간끝점·선점가능한용량·독립발열배치를허용한다. 실제일정을포함하는낙관적완화이므로 비용하한에서 최대절감상한을얻는다. LP해를 실행가능일정으로쓰지않는다. 모든변수의유한box에서쌍대잔차를보수적으로보정하고수치여유를뺀하한을독립JS로재계산했다. solver의primal이나탐색실패는상한근거가아니다.
- 각원EDF/ATC/RL trace를 LP에매핑해구조제약과조건부count제약을검사했다. 독립온도구간0.05℃·원RC상한41.7054℃·공유비용의owner당H/2 하한을쓴다. 열은같은RC식의에너지침착커널과상한전력으로완화했다. 수치적보수경계이며기기물리최적상한은아니다.

## 모든조건의달성량과최대가능상한

에너지 단위는EDF대비절감%, 온도는EDF대비하락℃다. 음수는악화다. 같은행의에너지/온도달성량은별개최선일정일수있다.

|배수|파형|납기층|필요전체/긴급정시|찾은에너지절감%|낙관적최대절감%|찾은온도하락℃|낙관적최대하락℃|공동목표일정수|
|---:|---|---|---:|---:|---:|---:|---:|---:|
${table}

숫자판정: ${JSON.stringify(counts)}. 상한이목표보다작으면 해당모형/입력/조건에서는목표가불가능하다. 큰개선의실행가능일정을찾으면현재정책에남은여지가있다. 둘사이간격이넓으면정확한최적값과원인비중은미결정이며 탐색실패를모형한계로승격하지않는다.

## 모든후보와손해

|조건|정책/일정|출처|전체정시|긴급정시|완료응답P95초|미응답/미완료|완료시간초|완료J*|고정공통평균AP℃|최고AP℃|비고|
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
${all}

## 검증·재개

82START/82COMPLETE/FAIL0·40LP·독립${audit.checks}검사/쌍대40건 PASS다. 새88예약중 잔6·기존coupled38/savings8/sustained4/density4/RR1은 미사용·추적125962/137712 snapshot이며 전host실시간집계는아니다. 원자료SHA·잠재양route계보·P0전trace/clock정확·적분/자원점유/원WAIT mask·P95와전체분모를검산했다. 결과RESULT/BOUNDS/EVALUATION/HEADROOM_SUMMARY/ALL_ROWS_WITH_REASONS, 각CERT/원시/receipt·AUDIT·최종파일SHA를같은폴더에보존한다. 새NN학습/물리fit/단말명령/자동추가실행0이다.
`;
fs.writeFileSync(path.join(out,'REPORT.md'),report,{flag:'wx'});
const concise=`같은밀도10입력·8오프라인일정×10＋정확P02=82완료/FAIL0·40LP/독립${audit.checks}검사다. EDF보존층 에너지10%불가능${counts.EDF.energy10_impossible}/10·평균온도.5℃불가능${counts.EDF.temperature_point5_impossible}/10·발견한공동목표${counts.EDF.found_joint}/10이다. STRONG층은EDF/RL최대정시수를보존한다. 정확최적값/온라인달성성/기기우위는미주장이다.`;
for(const [file,title] of [['docs/PROJECT_STATUS.md','A24 밀도 열·에너지 절감 여지 — 완료'],['docs/PROJECT_PLAN.md','같은모형 밀도 절감 여지 완료'],['docs/DECISIONS.md','A24-DENSITY-HEADROOM 완료']]){const p=path.join(repo,file);fs.writeFileSync(p,`## 2026-10-18 ${title}\n\n${concise}\n\n[모든상한·일정·손해](../a24_simulator/${op.output_dir}/REPORT.md). 새88잔6/기존잔불변·계수/입력/CP불변·학습/fit/기기0이다. 다음은해석/공유이며자동후속0·검증은OP SHA와최종proof를따른다.\n\n`+fs.readFileSync(p,'utf8'));}
const readme=path.join(root,'README.md');fs.writeFileSync(readme,`**같은모형 절감 여지:** [정본](${op.output_dir}/REPORT.md). ${concise}\n\n`+fs.readFileSync(readme,'utf8'));
const cont=path.join(root,'CONTINUE.json');fs.writeFileSync(cont,JSON.stringify({density_headroom:{status:'COMPLETED',operation:'experiments/density_headroom_20261018/OPERATION.json',report:op.output_dir+'/REPORT.md',new_START:82,LP_solves:40,counts},...read(cont)},null,2)+'\n');
const files=[...fs.readdirSync(out).map(f=>path.join(out,f)),...fs.readdirSync(__dirname).map(f=>path.join(__dirname,f)),...['docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/README.md','a24_simulator/CONTINUE.json','a24_simulator/docs/DENSITY_HEADROOM.md'].map(f=>path.join(repo,f))];
fs.writeFileSync(path.join(out,'FINAL_HANDOFF_PROOF.json'),JSON.stringify({utc:new Date().toISOString(),HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),new_START:82,LP_solves:40,files:files.map(p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size}))},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:'PUBLISHED',counts,aggregate,files:files.length}));
