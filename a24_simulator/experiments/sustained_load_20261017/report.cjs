'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),m=read(path.join(out,'WORK_METRICS.json')),audit=read(path.join(out,'AUDIT.json')),result=read(path.join(out,'RESULT.json'));
if(audit.result_sha256!==sha(path.join(out,'RESULT.json'))||audit.work_metrics_sha256!==sha(path.join(out,'WORK_METRICS.json')))throw Error('Audit pins');
for(const p of [...op.sources,...op.input_pins])if(sha(p.path)!==p.sha256)throw Error('Immutable pin '+p.path);
const f=(n,d=3)=>Number(n).toFixed(d),table=m.summary.map(r=>`|${r.supply_s}|${r.policy}|${r.requests}|${f(r.mean_completion_duration_s)}|${f(r.mean_completion_total_J_proxy)}|${f(r.completion_baseline_percent)}%|${f(r.completion_saving_percent)}%|${f(r.common_saving_percent)}%|${f(r.mean_supply_AP_c)}|${r.on_time}/${r.requests}|${r.urgent_on_time}/${r.urgent_planned}|${r.no_SLA_harm_every_case}|`).join('\n');
const all=m.rows.map(r=>`|${r.condition.supply_s}|${r.condition.pattern}|${r.policy}|${r.n}|${f(r.completion.duration_s)}|${f(r.completion.total_J_proxy)}|${f(r.completion.baseline_percent)}%|${f(r.supply.mean_AP_c)}|${f(r.last60_supply_mean_AP_c)}|${f(r.active_execution_mean_speed,4)}|${r.original.on_time}|${r.original.urgent_on_time}|${r.original.response_missing}/${r.original.incomplete}|`).join('\n');
const text=`# A24 요청 공급120·300·600초 비교

22초는 제한시간이 아니다. 이전 fresh12의48/96요청은 평균 약19초 동안 도착했고, EDF 마지막AVAILABLE까지 평균21.9419초였다. 요청량이 작아 열 시정수25초보다 짧은 과도상태를 주로 평가했다. 이번은 단순 관측 종료 연장이 아니라48요청 사이클을 반복해 요청 공급을120/300/600초 유지한다.

## 조건과 평가

C50%·기존 상대 납기/긴급도·두 파형(staggered_wave load.65/clustered_recovery load.95)·초기26℃·동일 열 피드백·CPU/GPU 각1을 고정했다. 같은 파형의 긴 조건은 짧은 조건과 정확히 같은 요청 및 잠재 작업량 prefix를 공유한다. 마지막 사이클 일부는 잘라서 분류/긴급 비율이 정확히50/25%가 아닐 수 있다. 정책마다 같은 요청을 모두 포함한다. 최대요청3072 조건을 지켰다.

EDF·ATC·원 DEV선정 RL(seed3701 EP064)을 동결했다. 새학습/물리fit/기기0이다. 모형의RC/DVFS/누설은 식별된 A24 물리값이 아니며 J*는 실측J가 아니다. 장시간 NN입력은 짧은학습 범위 밖이고 전체 WAIT예산12초·마스크/관측/명목예측은 원본 그대로다. 긴 부하로 재학습한 RL의 결론이 아니다. 과거 다른 모형의733초 결과와 혼합하지 않는다.

주 에너지는 첫도착35초부터 각정책 마지막AVAILABLE까지의 자기 완료 소비로, 작업 사이 유휴/WAIT를 포함한다. 총완료시간도 함께 보고한다. 같은3정책 최대AVAILABLE까지의 공통 종료 소비를 별도로 보고하고, 평균AP는 같은 요청공급120/300/600초 구간을 쓴다. 완료 후 활성 decay 약0.196J*는 별도필드에 남겼고 원 service/drain/observation 전체기록도 보존한다. 원 사전목표나 기존 절감한계를 소급 바꾸지 않는다.

## 두 파형 집계

에너지는 두조건 합계 대비 절감률, J*/완료시간/AP는 조건평균이다. 정시는 전체 도착 분모이며 납기 비악화는 각조건의 전체/긴급 정시개수와 미응답/미완료를 확인한다. 에너지 감소가 있어도 납기손해면 공동우위가 아니다.

|공급s|정책|요청합|완료창평균s|완료J*|기저비율|완료절감|공통절감|공급평균AP℃|전체정시|긴급정시|각조건 납기비악화|
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
${table}

## 모든18결과

speed는 공급 중 active실행시간 가중 평균 주파수비다. 마지막60초 평균AP로 계속 온도가 증가하는지 정상상태에 가까운지도 확인한다.

|공급s|파형|정책|요청|완료창s|완료J*|기저비율|공급AP℃|마지막60초AP℃|실행speed|전체정시|긴급정시|미응답/미완료|
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
${all}

## 검증과 경계

새별도24예약 중20START/20COMPLETE/FAIL0(정확P0 EDF/RL2＋새18), 잔4자동추가0이다. 원coupled잔38/savings잔8/RR잔1 불변·추적예약125790/137712 snapshot이다. 입력prefix/납기24계약, 원FRESH02 EDF/RL 요청별 경로·시각 정확동등성 P0, 독립 ${audit.checks}검사 PASS·NN ${audit.independent_NN_frames}frame 재생을 마쳤다. 최대 산술차 ${audit.max_absolute_error}다. 원시 모든 일정/후보/NN입력·checkpoint SHA와 Adam/RNG 불변증거를 보존했다.

이 비교는 길이를 늘렸을 때 세정책이 실제로 만든 차이를 측정하며 최적정책의 절감 상한을 새로 증명하지 않는다. 요청 수·총작업량도 함께 커지므로 길이 효과와 열 이력 효과를 완전히 분리한 인과실험은 아니다. 온도와 실행속도의 장시간 실기기 검증, 긴부하 전용 학습, 전체 최적값은 미확인이다.
`;
fs.writeFileSync(path.join(out,'REPORT.md'),text,{flag:'wx'});
const last=m.summary.filter(x=>x.supply_s===600),edf=last.find(x=>x.policy==='EDF'),rl=last.find(x=>x.policy==='RL'),atc=last.find(x=>x.policy==='ATC');
const concise=`현재 열피드백 모형에서120/300/600초 실제 요청공급을 비교했다. 600초 EDF기저${f(edf.completion_baseline_percent)}%·RL완료소비절감${f(rl.completion_saving_percent)}%/공급AP차${f(rl.mean_supply_AP_delta_c)}℃/정시Δ${rl.on_time_delta}, ATC절감${f(atc.completion_saving_percent)}%다. RL각조건납기비악화=${rl.no_SLA_harm_every_case}이며 모형내결과/고정단기NN외삽이다.`;
const prepend=(p,t)=>fs.writeFileSync(p,t+'\n\n'+fs.readFileSync(p,'utf8'));
prepend(path.join(repo,'docs/PROJECT_STATUS.md'),`## 2026-10-17 A24 지속 부하 — 20실행·독립검산 완료\n\n${concise}\n\n[모든조건/결과](../a24_simulator/${op.output_dir}/REPORT.md). ${audit.checks}저장검사·P0정확2·20완료/FAIL0, 새24잔4/원38·8·RR1불변·학습/fit/기기0다. 검증은OP SHA/새proof를 따른다. 다음은 결과 해석/공유이며 이번 유한 비교는 완료·자동후속0이다.`);
prepend(path.join(repo,'docs/PROJECT_PLAN.md'),`## 2026-10-17 지속 부하 비교 완료\n\n${concise}\n\n요청을 계속 넣어 평가 길이를 늘렸으며 모든18결과와 실패/미완료 분모를 [보고서](../a24_simulator/${op.output_dir}/REPORT.md)에 보존했다. 새로운 최적값/실기기 우위/원 사전목표 성공으로 승격하지 않는다.`);
prepend(path.join(repo,'docs/DECISIONS.md'),`## 2026-10-17 A24-SUSTAINED — 실제 요청공급 연장\n\n사용자22초보다 길게 요청에 따라 공급120/300/600초, C50두파형, 최대3072요청, 같은 prefix와 상대납기, 고정EDF/ATC/RL의 별도20실행을 채택/완료했다. ${concise}\n\n원시/물리/학습/과거절감상한은 보존하고 장시간 가설 외삽과 실제기기 검증을 구분한다. 근거: [보고서](../a24_simulator/${op.output_dir}/REPORT.md).`);
prepend(path.join(root,'README.md'),`**지속 요청공급120·300·600초 완료:** [모든정책·모든결과](${op.output_dir}/REPORT.md). ${concise}`);
const cont=read(path.join(root,'CONTINUE.json'));fs.writeFileSync(path.join(root,'CONTINUE.json'),JSON.stringify({sustained_load:{status:'COMPLETED',operation:'experiments/sustained_load_20261017/OPERATION.json',report:op.output_dir+'/REPORT.md',summary:m.summary,new_START:20,new_COMPLETE:20,new_training:0},...cont},null,2)+'\n');
const docs=['docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/README.md','a24_simulator/CONTINUE.json'].map(p=>path.join(repo,p));
const files=[...fs.readdirSync(out).map(f=>path.join(out,f)),...fs.readdirSync(__dirname).map(f=>path.join(__dirname,f)),...docs];
const proof={utc:new Date().toISOString(),HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),uncommitted_changes:true,
 result_sha256:sha(path.join(out,'RESULT.json')),audit_sha256:sha(path.join(out,'AUDIT.json')),files:files.map(p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size})),new_START:20,new_COMPLETE:20};
fs.writeFileSync(path.join(out,'FINAL_HANDOFF_PROOF.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({summary:m.summary,files:proof.files.length}));
