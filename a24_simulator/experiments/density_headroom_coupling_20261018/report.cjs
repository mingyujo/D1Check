'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const save=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'}),f=(x,n=3)=>x==null?'미정의':Number(x).toFixed(n);
const same=require('node:util').isDeepStrictEqual;
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),parent=path.join(root,op.parent_output),data=read(path.join(out,'EVALUATION.json')),audit=read(path.join(out,'AUDIT.json'));
if(audit.status!=='PASS'||audit.evaluation_sha256!==sha(path.join(out,'EVALUATION.json')))throw Error('Require current saved audit');
const oldSummary=read(path.join(parent,'HEADROOM_SUMMARY.json')),allRows=read(path.join(parent,'ALL_ROWS_WITH_REASONS.json')),proofs=read(path.join(out,'PHASE_PROOFS.json')).rows;
if(!same(data.rows,read(path.join(parent,'EVALUATION.json')).rows)||allRows.rows.length!==112)throw Error('All rows must be retained');
const summaries=oldSummary.cases.map(s=>{
 const e=data.bounds.find(b=>b.case===s.case&&b.tier===s.tier&&b.kind==='energy'),t=data.bounds.find(b=>b.case===s.case&&b.tier===s.tier&&b.kind==='temperature');
 return {...s,old_maximum_energy_saving_percent:s.maximum_energy_saving_percent,old_maximum_temperature_reduction_c:s.maximum_temperature_reduction_c,
  maximum_energy_saving_percent:e.maximum_reduction,maximum_temperature_reduction_c:t.maximum_reduction,
  energy10_impossible_by_relaxation:e.maximum_reduction<10,temperature_point5_impossible_by_relaxation:t.maximum_reduction<.5};
});
const aggregate=[];
for(const tier of ['EDF','STRONG'])for(const factor of [.5,1,1.5,2,3]){
 const g=summaries.filter(s=>s.tier===tier&&s.condition.rate_multiplier===factor),B=g.reduce((a,s)=>a+s.reference_EDF_completion_J,0),a={tier,factor};
 for(const key of ['achieved_energy_saving_percent','maximum_energy_saving_percent','old_maximum_energy_saving_percent'])a[key]=g.reduce((a,s)=>a+s.reference_EDF_completion_J*s[key],0)/B;
 for(const key of ['achieved_temperature_reduction_c','maximum_temperature_reduction_c','old_maximum_temperature_reduction_c'])a[key]=g.reduce((a,s)=>a+s[key],0)/g.length;
 a.feasible_choices_are_posthoc_per_case_portfolios=true;aggregate.push(a);
}
const counts=Object.fromEntries(['EDF','STRONG'].map(t=>[t,{energy10_impossible:summaries.filter(s=>s.tier===t&&s.energy10_impossible_by_relaxation).length,
 temperature_point5_impossible:summaries.filter(s=>s.tier===t&&s.temperature_point5_impossible_by_relaxation).length,
 found_joint:summaries.filter(s=>s.tier===t&&s.feasible_joint_targets.length).length}]));
const decomposition=summaries.map(s=>{
 const local=data.rows.filter(r=>r.case===s.case),edf=local.find(r=>r.source==='ORIGINAL'&&r.policy==='EDF'),rl=local.find(r=>r.source==='ORIGINAL'&&r.policy==='RL'),best=local.find(r=>r.label===s.feasible_energy);
 return {case:s.case,tier:s.tier,feasible_energy:best.label,completion_earlier_s:edf.completion.duration_s-best.completion.duration_s,
  total_saving_J:edf.completion.total_J_proxy-best.completion.total_J_proxy,
  baseline_saving_J:edf.completion.baseline_J_proxy-best.completion.baseline_J_proxy,
  increment_saving_J:edf.completion.increment_J_proxy-best.completion.increment_J_proxy,
  EDF_baseline_percent:100*edf.completion.baseline_fraction,best_baseline_percent:100*best.completion.baseline_fraction,
  RL_satisfies_tier:Object.entries(s.targets).every(([k,v])=>rl.original[k]>=v),RL_total_J:rl.completion.total_J_proxy,best_total_J:best.completion.total_J_proxy,
  RL_minus_best_J:rl.completion.total_J_proxy-best.completion.total_J_proxy,
  optimistic_unresolved_energy_gap_percent:s.maximum_energy_saving_percent-s.achieved_energy_saving_percent};
});
for(const d of decomposition)if(Math.abs(d.total_saving_J-d.baseline_saving_J-d.increment_saving_J)>1e-7)throw Error('Energy decomposition conservation');
save(path.join(out,'HEADROOM_SUMMARY.json'),{cases:summaries,aggregate,counts,decomposition,online_policy_claim:false,global_optimum_found:false});
fs.copyFileSync(path.join(parent,'ALL_ROWS_WITH_REASONS.json'),path.join(out,'ALL_ROWS_WITH_REASONS.json'),fs.constants.COPYFILE_EXCL);
const brackets=summaries.map(s=>`|${s.condition.rate_multiplier}|${s.condition.pattern}|${s.tier}|${s.targets.on_time}/${s.targets.urgent_on_time}|${f(s.achieved_energy_saving_percent)}|${f(s.old_maximum_energy_saving_percent)} → ${f(s.maximum_energy_saving_percent)}|${f(s.achieved_temperature_reduction_c)}|${f(s.old_maximum_temperature_reduction_c)} → ${f(s.maximum_temperature_reduction_c)}|${s.feasible_joint_targets.length}|`).join('\n');
const choices=summaries.map(s=>`|${s.case}|${s.tier}|${s.feasible_energy}|${s.feasible_heat}|${f(s.best_energy_temperature_reduction_c)}|${f(s.best_heat_energy_saving_percent)}|`).join('\n');
const boundTable=data.bounds.map(b=>`|${b.case}|${b.tier}|${b.kind}|${b.status}|${b.new_status}|${b.new_dual_available}|${f(b.old_maximum_reduction,6)}|${f(100*(1-b.new_coupled_lower/b.reference_EDF)*(b.kind==='energy')+(b.reference_EDF-b.new_coupled_lower)*(b.kind!=='energy'),6)}|${f(b.maximum_reduction,6)}|${b.selected_bound==='original dual retained'?'기존 하한 유지: 새 보정 하한이 더 낮음':'새 결합 하한 채택'}|`).join('\n');
const all=allRows.rows.map(r=>`|${r.case}|${r.policy}|${r.source}|${r.original.on_time}/${r.n}|${r.original.urgent_on_time}/${r.original.urgent_planned}|${f(r.original.P95_completed_response_s)}|${r.original.response_missing}/${r.original.incomplete}|${f(r.completion?.duration_s)}|${f(r.completion?.total_J_proxy)}|${f(r.common.mean_AP_c)}|${f(r.original.peak_AP_c)}|${r.remarks.join('; ')}|`).join('\n');
const barrier=proofs.map(p=>`|${p.case}|${f(p.original_upper,6)}|${f(p.upper,6)}|${f(p.routes.CPU.rho,6)}|${f(p.routes.GPU.rho,6)}|${f(p.convolution_burst_c,6)}|`).join('\n');
const deadlineTable=read(path.join(out,'ALL_DEADLINE_CAPACITY.json')).rows.map(c=>`|${c.case}|${c.all_arrivals}|${c.minimum_non_on_time_proved}|${c.all_on_time_ruled_out?'전요청정시 불가능: 냉간 최단작업도 2자원 용량 초과':'필요조건만으로 불가능 판정 못함; 가능성 입증 아님'}|`).join('\n');
const decompositionTable=decomposition.map(d=>`|${d.case}|${d.tier}|${f(d.total_saving_J)}|${f(d.baseline_saving_J)}|${f(d.increment_saving_J)}|${f(d.completion_earlier_s)}|${f(d.EDF_baseline_percent)}|${f(d.RL_minus_best_J)}|${f(d.optimistic_unresolved_energy_gap_percent)}|`).join('\n');
const text=`# 같은 모형의 절감 여지: 실행 가능한 일정과 좁힌 상한

원밀도10입력·도착·납기·잠재작업·물리계수와82개 새 실행을 모두 고정했다. [첫 진단](../${path.basename(parent)}/REPORT.md)의40개 LP 뒤, 저장 자료만으로40개 LP를 추가하여 열·에너지 결합 필요조건과 작업단계 길이를 반영했다. 추가 native/학습/fit/타이밍은행복원/실기기0이다. 새 물리 효과나 온도 clip을 넣은 결과가 아니다.

![찾은 개선과 최대 가능 상한](HEADROOM.png)

## 해석

찾은 일정은 실제 원engine에서 실행한 오프라인 진단 일정이다. 발견한 최선 절감은 달성 하한, 낙관적 완화의 비용하한으로부터 얻은 최대 절감은 달성 상한이다. 그 사이가 넓으면 최적값과 모형/정책 원인 비율은 미결정이다. 검색한 일정이 절감하지 못한 사실만으로 모형이 불가능하다고 판정하지 않는다. 모든112개 일정과40개 기존/신규 LP 결과를 아래 남겼으며 삭제0이다.

- EDF층: 원EDF의 전체정시와 긴급정시 수를 각각 보존. STRONG층: 원EDF/RL 중 큰 값을 각각 보존. 전요청 정시를 뜻하지 않는다. 미응답/미완료는 모두0이어야 적격이다.
- 에너지: 첫공급35초부터 자기 마지막AVAILABLE까지 기저＋증분J*. 완료는 원drain785초 이내. 온도: 원3정책의 공통완료시각을 고정한 창이며, 그시각까지 모든작업을 완료한 일정만 열우위 선정에 쓴다. 열상한은 이 더빠른 완료시한 조건의 상한이다.
- 최저에너지 일정과 최저온도 일정은 다를 수 있다. 공동10%/.5℃는 반드시 같은 납기적격·온도창완료 일정에서 확인한다. 조건별 사후최선 묶음은 한 온라인정책 성능이 아니다. 미래 실현작업량을 아는 일정을 온라인 달성성이나 새RL 우위로 해석하지 않는다.
- J*/AP는 현재 A24 가설모형의 출력이다. 실측 에너지·실기기 최적한계가 아니다. 원정책/NN/보상/물리/입력을 바꾸지 않았다.

## 달성량과 상한: 모든20조건

에너지 단위는EDF대비%, 온도는EDF대비하락℃다. 음수는악화. 상한은 기존→강화후 순서다.

|배수|파형|납기층|필요전체/긴급정시|찾은에너지절감%|낙관적최대절감%|찾은온도하락℃|낙관적최대하락℃|공동목표일정수|
|---:|---|---|---:|---:|---:|---:|---:|---:|
${brackets}

각 최선일정의 식별자를 아래 공개한다. 정확한 request별 route/dispatch/response/AVAILABLE는 원 보고서의 raw_path 및 ALL_ROWS_WITH_REASONS에 연결되어 있다. 에너지최선이 온도완료창을 넘기면 그일정의 온도개선은 미정의다.

|조건|납기층|에너지최선 일정|온도최선 일정|에너지최선의온도하락℃|온도최선의에너지절감%|
|---|---|---|---|---:|---:|
${choices}

수치판정 ${JSON.stringify(counts)}. 정확한 전역최적은 미확인이다. 최대절감상한<10% 또는 최대온도하락<.5℃이면 그 조건의 목표는 이 모형에서 불가능하다. 에너지·열 각각 큰상한은 둘의 동시달성을 증명하지 않는다. 이전 판정과 범위를 소급변경하지 않는다.

전체요청을 전부정시로처리하는 해석도 별도로 확인했다. release≥a 및 deadline≤b인 요청의 가장빠른route 냉간응답prefix 합은 2(b−a) 이하여야 한다. 각구간의 초과분에서 큰작업부터 빼도 남는 최소 미정시수를 구했다. 양route분할/냉간속도/무열/응답후suffix0까지 유리하게 허용한 필요조건이다. 양수이면 전요청정시는 불가능, 0이면 이 검사로 결정할수없다. 모든구간 수치는 ALL_DEADLINE_CAPACITY에 남겼다.

|조건|전체도착|최소미정시수 증명|비고|
|---|---:|---:|---|
${deadlineTable}

## 소비 차이의 기저/증분 분해

EDF−적격에너지최선의 절감J*를 기저와 증분으로 나눴다. 음수는 악화이며 조기완료만으로 생긴 절감도 숨기지 않는다. RL−최선J*는 같은전체/긴급정시를 RL이 충족하는지 HEADROOM_SUMMARY에 함께 표시한다. STRONG층 최선은 RL 정시수를 모두 보존한다. 마지막열은 아직풀리지않은 에너지 절감 간격(상한−찾은값)으로, 실제 달성가능하다는 뜻이 아니다.

|조건|납기층|총절감J*|기저절감J*|증분절감J*|조기완료초|EDF기저비율%|RL−최선J*|미결정절감간격%p|
|---|---|---:|---:|---:|---:|---:|---:|---:|
${decompositionTable}

## 모형을 고치지 않고 상한을 좁힌 근거

같은 RC식에서 A=∫(T−26)dt, E=증분에너지, D=창길이, U=온도상한−26이면 A=R E−τ(T끝−26)이다. 실행작업 W를 온도구간[lo,hi]에 놓을 때, 최대2owner와 active step≤0.1초로부터 다음 필요조건을 더했다. 온도는 step시작값을 쓰므로 |T′|의 보수적 상한 L을 써서 step오차를 유리하게 더한다. ns phase올림도 별도 여유로 포함한다.

    Σ (lo−26) W/fmax ≤ 2A + L tick D + ε
    2A ≤ 2U D + Σ [(hi−26)/fmin − U/fmax] W + L tick D + ε

에너지는 실제증분 변수 e≥기존 작업에너지하한과 R e−τU≤A≤R e를 연결했다. 열은 원1초-bin 에너지침착의 RC 상·하 커널로 A를 감쌌다. 각bin종료 온도도 작업단계 상한이하여야 하므로 bin에너지를 유리한 시작점으로옮긴 낮은RC끝온도≤U를 추가했다. 열을 끝에몰아 실제상한을넘기는 완화도 방지한다. 두LP 모두 동일 온도가 시간·전력·열에서 가져오는 필수연결만 추가했으며 실제 스케줄보다 유리한 분할/선점/침착 자유는 여전히 허용한다.

원41.705℃ 상한은 비실행 단계가 계속되는 상태까지 포함한다. 하지만 한 비선점 작업에서 비실행시간 N은 고정되어 있고 실행시간은 원실행작업 W 이상이다. route별 ρ=max N/(N+W), b=2 max N으로 잡으면 모든길이 l의 구간에서 비실행시간≤ρ l+b이다. 최대두개의 경계작업이 부분적으로 걸리는 경우까지 b에 포함한다. RC의 지수커널에 이 필요조건을 적분하면 비실행의 추가발열은 δ[ρτ(1−exp(−l/τ))+b] 이하이다.

실행발열의 온도미분이 음수인 범위를 독립계산하고, step시작 온도오차 η=L tick를 포함한 교차온도 B=26+R[Pexec(B−η)+Σδρ]를 구했다. 초기26℃에서 B를 마지막으로 통과한 시각을 잡으면 이후 온도는 B+(R/τ)Σδb 이하이다. 1e−6℃를 추가하고 원상한과 작은 값을 취했다. 이는 주어진 작업은행의 임의순서/WAIT를 포함하는 열방정식의 상한이며 시뮬레이터에 온도를 잘라넣지 않았다. 소스 Python과 별개 JS로 계수·근·도함수·단계길이를 다시 계산하고 기존112개 최고온도가 모두 안에 있음을 확인했다.

|조건|원상한℃|작업단계 반영상한℃|CPU비실행비율상한|GPU비실행비율상한|경계burst여유℃|
|---|---:|---:|---:|---:|---:|
${barrier}

모든 LP는 유한box의 쌍대잔차를 보정한 하한에서 수치여유를 뺀다. JS가 모든40인증을 독립재계산했다. 새 쌍대가 약해지면 원하한을 유지하고 그이유를 아래 표시한다. solver primal이나 탐색실패를 절감상한으로 쓰지 않는다.

## 모든40개 상한 비교와 solver 상태

에너지행은%, temperature행은℃. status0은 solver 최적종료, 나머지상태도 숨기지 않는다. 채택값은 두 유효하한 중 큰 값에서 계산한다.

|조건|납기층|종류|기존status|새status|새쌍대사용가능|기존최대절감|새결합만의최대절감|채택최대절감|비고|
|---|---|---|---:|---:|---|---:|---:|---:|---|
${boundTable}

## 모든112개 일정과 제외사유

원새82개(재현2 포함)＋기준30개를 그대로 표시한다. 납기부족·온도창을넘긴완료·재현용 구분은 비고에 남기며 행을 제거하지 않는다. 완료P95와 전체 도착/긴급 분모, 미응답/미완료를 함께 제공한다.

|조건|정책/일정|출처|전체정시|긴급정시|완료응답P95초|미응답/미완료|완료시간초|완료J*|고정공통평균AP℃|최고AP℃|비고|
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
${all}

## 검증과 재개

첫등록82START/82COMPLETE/FAIL0·40LP·원독립감사를 보존하고, 이번은 saved-only40LP/독립${audit.checks}검사 PASS·실행행112완전동일·삭제0이다. 전체 LP80, native82이고 새88예약잔6 및 기존잔38/8/4/4/RR1을 더쓰지 않았다. 전역추적125962/137712는 과거snapshot이며 전host실시간집계가 아니다. 원완료op·실패·원상한/보고서는 보존하며 자동추가/재시도0이다. 현재정본은 이 보고서와 HEADROOM_SUMMARY/ALL_ROWS_WITH_REASONS/EVALUATION, 각CERT/PHASE_PROOFS/AUDIT/FINAL_HANDOFF_PROOF다.
`;
fs.writeFileSync(path.join(out,'REPORT.md'),text,{flag:'wx'});
const concise=`같은10밀도입력의 native82완료·LP총80 및 독립저장검산 PASS다. EDF층 에너지10%불가능${counts.EDF.energy10_impossible}/10·평균온도.5℃불가능${counts.EDF.temperature_point5_impossible}/10·발견공동목표${counts.EDF.found_joint}/10. 작업단계/열·전력 필요조건으로 상한만 강화했고 모형/입력/NN불변·새native0이다. 모든112일정과40쌍의신구상한·선정제외이유를 공개한다.`;
for(const [file,title] of [['docs/PROJECT_STATUS.md','A24 같은모형 절감 여지 — 결합상한 검산 완료'],['docs/PROJECT_PLAN.md','같은모형 절감 여지 결합상한 완료'],['docs/DECISIONS.md','A24-DENSITY-HEADROOM 결합상한 완료']]){
 const p=path.join(repo,file);fs.writeFileSync(p,`## 2026-10-18 ${title}\n\n${concise}\n\n[전결과/상한/비고](../a24_simulator/${op.output_dir}/REPORT.md). 정확최적/온라인달성/기기우위 미확인·새88잔6/기존잔여불변·학습/fit/기기0이다. 다음은해석/공유·자동후속0이며검증은이번OP SHA와최종proof를따른다.\n\n`+fs.readFileSync(p,'utf8'));
}
const rp=path.join(root,'README.md');fs.writeFileSync(rp,`**같은모형 결합상한 정본:** [모든결과](${op.output_dir}/REPORT.md). ${concise}\n\n`+fs.readFileSync(rp,'utf8'));
const cont=path.join(root,'CONTINUE.json');save(path.join(out,'CONTINUE_PREVIOUS.json'),read(cont));fs.writeFileSync(cont,JSON.stringify({density_headroom_coupled:{status:'COMPLETED',operation:'experiments/density_headroom_coupling_20261018/OPERATION.json',report:op.output_dir+'/REPORT.md',new_START:0,new_LP_solves:40,counts},...read(cont)},null,2)+'\n');
const files=[...fs.readdirSync(out).map(f=>path.join(out,f)),...fs.readdirSync(__dirname).filter(f=>fs.statSync(path.join(__dirname,f)).isFile()).map(f=>path.join(__dirname,f)),...['docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/README.md','a24_simulator/CONTINUE.json'].map(f=>path.join(repo,f))];
save(path.join(out,'FINAL_HANDOFF_PROOF.json'),{utc:new Date().toISOString(),HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),new_START:0,new_LP_solves:40,
 parent_proof_sha256:sha(path.join(parent,'FINAL_HANDOFF_PROOF.json')),parent_historical_docs_preserved_at_previous_result_commit:true,
 files:files.map(p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size}))});
console.log(JSON.stringify({status:'PUBLISHED',counts,aggregate,files:files.length}));
