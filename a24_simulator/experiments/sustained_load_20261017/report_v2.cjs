'use strict';
// Saved-only publication; completion is undefined when overload leaves requests.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),amend=read(path.join(__dirname,'SAVED_AUDIT_V2.json')),out=path.join(root,amend.report_output_dir),m=read(path.join(out,'WORK_METRICS.json')),audit=read(path.join(out,'AUDIT.json')),result=read(path.join(out,'RESULT.json')),diag=read(path.join(out,'CHOICE_DIAGNOSIS.json'));
const reportDir=amend.report_output_dir;
if(audit.result_sha256!==sha(path.join(out,'RESULT.json'))||audit.work_metrics_sha256!==sha(path.join(out,'WORK_METRICS.json'))||diag.result_sha256!==sha(path.join(out,'RESULT.json')))throw Error('Audit pins');
for(const p of [...op.sources,...op.input_pins,...amend.sources,...amend.inputs])if(sha(p.path)!==p.sha256)throw Error('Immutable pin '+p.path);
const f=(n,d=3)=>n==null?'미정의':Number(n).toFixed(d);
const table=m.summary.map(r=>`|${r.supply_s}|${r.policy}|${r.requests}|${f(r.mean_supply_total_J_proxy)}|${f(r.supply_saving_percent)}%|${f(r.supply_baseline_percent)}%|${f(r.mean_supply_AP_c)}|${r.on_time}/${r.requests}|${r.urgent_on_time}/${r.urgent_planned}|${r.response_missing}/${r.incomplete}|${f(r.completion_saving_percent)}|`).join('\n');
const all=m.rows.map(r=>`|${r.condition.supply_s}|${r.condition.pattern}|${r.policy}|${r.n}|${f(r.completion?.duration_s)}|${f(r.completion?.total_J_proxy)}|${f(r.supply.total_J_proxy)}|${f(r.supply.mean_AP_c)}|${f(r.last60_supply_mean_AP_c)}|${r.original.on_time}|${r.original.urgent_on_time}|${f(r.original.P95_completed_response_s)}|${r.original.response_missing}/${r.original.incomplete}|`).join('\n');
const choice=diag.rows.filter(r=>r.policy==='EDF').map(r=>`|${r.condition.supply_s}|${r.condition.pattern}|${r.dispatches}/${r.n}|${f(r.multiple_ready_percent)}%|${f(r.both_routes_free_percent)}%|${f(r.wait_s)}|`).join('\n');
const text=`# A24 요청 공급120·300·600초 비교

22초는 제한시간이 아니다. 이전 fresh12의48/96요청은 평균 약19초 동안 도착했고 EDF 마지막AVAILABLE까지 평균21.9419초였다. 이번은 실제 요청을120/300/600초 동안 계속 공급한 별도 실험이다. 원모형/계수/CP와 기존 결과는 변경하지 않았다.

## 조건

C50% 원48요청 cycle·두 파형(staggered_wave load.65/clustered_recovery load.95)·초기26℃·같은 상대납기/긴급도·열 피드백·CPU/GPU 각1을 고정했다. 같은 파형의 길이별 공개 요청과 잠재 작업량 key prefix가 같다. 마지막 일부 cycle을 잘라서 전체 C/U 비율은 정확히50/25%가 아닐 수 있다. 최대2352요청으로 사용자3072한도를 지켰다.

EDF·ATC·원DEV선정 RL(seed3701 EP064, 원DEV qualification=false)을 동결했다. 새학습/fit/기기0이다. 긴부하에서 재학습한 RL이 아니며 시간/큐/명목입력은 단기학습 범위 밖 외삽이다. 전체 WAIT예산12초·관측/마스크/실제 및 명목 적분은 그대로다. 과거 다른 모형733초 결과와 합치지 않는다. 열RC/DVFS/누설은 A24 식별값이 아니고 J*는 실측J가 아니다.

## 지표와 미완료 처리

- 공급 소비/AP: 같은 첫도착35초부터 공급 종료까지120/300/600초의 적분이다. 작업 사이 유휴/WAIT도 포함한다. 스트리밍 구간 소비로서 보고하되, 처리량/미완료가 다르면 효율 우위로 판정하지 않는다.
- 자기 완료 소비: 모든 요청의 마지막AVAILABLE까지 에너지와 시간이다. 요청이 끝내 배정되지 않거나 미완료면 **미정의/null**이다. 미완료 작업을 제외하고 완료 소비를 계산하지 않는다. 완료 후 공유활성 decay 약0.196J*는 별도필드에 남겼다.
- 공통 소비: 세정책 모두 완료하면 최대AVAILABLE까지 같은 창이다. 하나라도 미완료면 사전등록 drain까지 공통 적분하며 이를 fallback 필드로 표시한다. 이때도 처리량이 달라 절감 우위로 해석하지 않는다.
- 원서비스 종료는 공급+15초, drain은 공급+45초, 관측은 공급+195초다. 서비스 종료 뒤에는 새 배정을 하지 않는다. 긴 밀집부하가 이 시각까지 해소되지 못하면 미응답/미완료로 남긴다. 이를 숨기거나 결과를 본 뒤 시간을 늘려 재실행하지 않았다.
- 전체 도착 분모의 전체/긴급 정시, 완료 응답P95, 미응답·미완료는 원metrics에 모두 보존했다. 미응답을 제외한 성공률을 쓰지 않는다.

## 두 파형 집계

에너지/AP는 조건평균, 공급 절감률은 EDF 두조건 합계 대비 기술값이다. 완료 절감(%)은 해당 길이의 모든3정책/모든조건이 완료됐을 때만 정의한다. 음수 절감은 소비 증가다. 미완료가 있는 행의 공급 절감을 에너지 효율 우위로 쓰면 안 된다.

|공급s|정책|도착합|공급J*|공급절감 기술값|기저비율|공급AP℃|전체정시|긴급정시|미응답/미완료|완료절감%|
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
${table}

## 모든18결과

미정의는 계산오류가 아니라 전체 작업 완료가 성립하지 않은 경우다. 마지막60초AP로 장시간 정상상태에 가까워지는지도 본다.

|공급s|파형|정책|도착|완료창s|완료J*|공급J*|공급AP℃|마지막60초AP℃|전체정시|긴급정시|완료응답P95초|미응답/미완료|
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
${all}

## 길이와 경쟁 기회의 구분

아래는 EDF의 실제 배정 직전 상태다. 동일 도착밀도로 길이만 늘리면 경쟁 빈도가 반드시 늘지는 않는다. 밀집부하는 처리 지연과 대기열이 누적될 수 있다. 관측된 정책 상태이며 가능한 모든 정책의 선택 기회 상한은 아니다.

|공급s|파형|배정/도착|복수ready|CPU/GPU 둘다유휴|WAIT초|
|---:|---|---:|---:|---:|---:|
${choice}

## 검증과 계보

새24예약의 native는20START/20COMPLETE/환경FAIL0(정확P0 EDF/RL2＋새18), 잔4자동추가0이다. 원runner는18완료 후 외부의 일시Python 때문에 START19 전 전역leaf상한에서 종료됐고 FAILURE를 보존했다. 미시작2개만 별도continuation identity로 실행해20을 채웠다. 원18/P0재실행0·새전역예약0·frozen bank복원총2/fit0이다. 원coupled잔38/savings잔8/RR잔1불변·추적예약125790/137712 snapshot이다. 별도보고root의 raw는 두원본의SHA동일 복사본이고 MERGE_MANIFEST에 원경로/해시를 고정했다.

입력prefix/상대납기24계약, 원FRESH02 EDF/RL 경로/시각 정확재현, 독립 ${audit.checks}검사 PASS·NN ${audit.independent_NN_frames}frame argmax 재생을 마쳤다. 독립 에너지/RC/배타점유/latent 단계 작업량 검산 최대차 ${audit.max_absolute_error}다. 길이별 admission prefix ${diag.admission_prefix_checks}개·같은실행경로의 latent prefix ${diag.same_route_work_prefix_checks}개가 일치했다. 원18의 최종RNG/counter runtime확인은 종료로 도달하지 못했으므로 모든저장frame의 고정network digest/collect=false·고정CP 행동재생·no-update소스를 근거로 구분한다. 이어진2개는 종료runtime불변도 확인했다.

긴 밀집부하에서 미완료를 확인해 **실행은 그대로 보존하고 저장 후처리만 V2로 명시 수정**했다. 원audit.py/report.cjs는 실행0인 채 보존한다. V1은 미완료시 drain소비를 completion필드에 넣을 수 있어 미정의 처리와 집계 제외가 필요했다. V2에는 공급 경계의 평균실행속도 clip도 바로잡았다. 별도 SAVED_AUDIT_V2.json에 소스/정확RESULT SHA를 고정했다. 새환경/재시도/학습/계수 변경0이다.

이 비교는 현재 세정책의 실제 차이이며 장시간 최적정책의 절감 상한을 증명하지 않는다. 길이/총작업량/열/고정NN의 horizon 반응을 완전히 분리한 인과실험도 아니다. 기존 단기 고정창3.9828%·자기완료13.8136% 상한을 이 긴 입력에 전용하지 않는다. 원10%/.5℃ 공동목표의 소급 성공·실기기 우위·장시간 학습 수렴은 주장하지 않는다.
`;
fs.writeFileSync(path.join(out,'REPORT.md'),text,{flag:'wx'});
const last=m.summary.filter(x=>x.supply_s===600),edf=last.find(x=>x.policy==='EDF'),rl=last.find(x=>x.policy==='RL'),atc=last.find(x=>x.policy==='ATC');
const concise=`120/300/600초 실제 요청공급20실행을 완료했다. 600초 전체정시 EDF${edf.on_time}/ATC${atc.on_time}/RL${rl.on_time} (${edf.requests}도착), 미완료 ${edf.incomplete}/${atc.incomplete}/${rl.incomplete}다. 공급기저 EDF${f(edf.supply_baseline_percent)}%·RL 공급소비절감 기술값${f(rl.supply_saving_percent)}%/AP차${f(rl.mean_supply_AP_delta_c)}℃다. 미완료 조건의 전체완료 소비는 미정의이고 효율우위 판정은 보류한다.`;
const prepend=(p,t)=>fs.writeFileSync(p,t+'\n\n'+fs.readFileSync(p,'utf8'));
prepend(path.join(repo,'docs/PROJECT_STATUS.md'),`## 2026-10-17 A24 지속 부하 — 20실행·독립검산 완료\n\n${concise}\n\n[모든조건/결과](../a24_simulator/${reportDir}/REPORT.md). ${audit.checks}저장검사·P0정확2·native18＋미시작2正常/환경FAIL0, 원runner중단보존·추가전역예약0·새24잔4/원38·8·RR1불변·학습/fit/기기0다. 미완료후처리별도V2 SHA·기소비native재실행0이다. 다음은 해석/공유이며 비교완료·자동후속0이다.`);
prepend(path.join(repo,'docs/PROJECT_PLAN.md'),`## 2026-10-17 지속 부하 비교 완료\n\n${concise}\n\n[모든결과](../a24_simulator/${reportDir}/REPORT.md). 길이만늘려 열이 무한증가하거나 에너지격차가 커지는 것은 아니다. 밀집부하의 납기차이/미완료와 동결단기NN 외삽을 구분하며 새 최적값·원목표 성공을 주장하지 않는다.`);
prepend(path.join(repo,'docs/DECISIONS.md'),`## 2026-10-17 A24-SUSTAINED 완료·미완료 지표 정정\n\n${concise}\n\nnative18완료후 전역guard로START19전 중단, 미시작2만 별도identity로 실행하고 원FAILURE를 보존했다. 계수/입력/납기/서비스창/CP는불변이다. 완료에너지null의 저장후처리V2는별도SHA이며 원V1후처리실행0·새환경0이다. 근거: [보고서](../a24_simulator/${reportDir}/REPORT.md).`);
prepend(path.join(root,'README.md'),`**지속 요청공급120·300·600초 완료:** [모든정책/미완료/검산](${reportDir}/REPORT.md). ${concise}`);
const cont=read(path.join(root,'CONTINUE.json'));fs.writeFileSync(path.join(root,'CONTINUE.json'),JSON.stringify({sustained_load:{status:'COMPLETED_WITH_OVERLOAD_CENSORING',operation:'experiments/sustained_load_20261017/OPERATION.json',continuation_operation:'experiments/sustained_load_20261017/CONTINUATION_OPERATION.json',saved_audit_v2:'experiments/sustained_load_20261017/SAVED_AUDIT_V2.json',report:reportDir+'/REPORT.md',summary:m.summary,new_START:20,new_COMPLETE:20,new_training:0,original_runner_failure_preserved:true},...cont},null,2)+'\n');
const docs=['docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/README.md','a24_simulator/CONTINUE.json','a24_simulator/docs/SUSTAINED_LOAD.md'].map(p=>path.join(repo,p));
const files=[...fs.readdirSync(out).map(f=>path.join(out,f)),...fs.readdirSync(__dirname).map(f=>path.join(__dirname,f)),...docs];
const proof={utc:new Date().toISOString(),command:process.argv,HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),uncommitted_changes:true,
 result_sha256:sha(path.join(out,'RESULT.json')),audit_sha256:sha(path.join(out,'AUDIT.json')),files:files.map(p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size})),new_START:20,new_COMPLETE:20};
fs.writeFileSync(path.join(out,'FINAL_HANDOFF_PROOF.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({summary:m.summary,files:proof.files.length}));
