'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),pin=p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size});
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir);
const result=read(path.join(out,'RESULT.json')),audit=read(path.join(out,'AUDIT.json')),metricAudit=read(path.join(out,'SAVED_METRIC_AUDIT.json'));
const a=read(path.join(out,'ANALYSIS.json')),g=read(path.join(out,'GOAL_CHECKS.json')),choices=read(path.join(out,'CHOICE_DIAGNOSTICS.json')),fig=read(path.join(out,'FIGURES.json'));
if(result.new_START!==602||result.new_COMPLETE!==602||result.new_FAIL!==0||audit.result_sha256!==sha(path.join(out,'RESULT.json'))||metricAudit.result_sha256!==sha(path.join(out,'RESULT.json')))throw Error('Requires exact audited completion');
if(fs.existsSync(path.join(out,'FINAL_HANDOFF_PROOF.json')))throw Error('Finalization already consumed');
const fixed=n=>Number(n).toFixed(4),signed=n=>(n>=0?'+':'')+Number(n).toFixed(4),selected=a.selected_name,sel=a.selection.selected;
const header='| 정책 | 평균 총 J* | 작업 증분 J* | 평균 열 proxy ℃ | 정시/전체 | 긴급 정시/전체 | 미응답/미완료 |\n|---|---:|---:|---:|---:|---:|---:|';
const table=a.means.map(m=>`| ${m.policy===selected?'**'+m.policy+' (DEV선정)**':m.policy} | ${fixed(m.mean_total_J_proxy)} | ${fixed(m.mean_increment_J_proxy)} | ${fixed(m.mean_AP_c)} | ${m.on_time}/${m.planned} | ${m.urgent_on_time}/${m.urgent_planned} | ${m.response_missing}/${m.incomplete} |`).join('\n');
const nn='| seed | exact와 동일한 조건 | 자원 변경 요청 | 배정시각 변경 요청 | 같은 상태의 다른 행동/복수행동 판단 |\n|---|---:|---:|---:|---:|\n'+a.trajectories.map(t=>`| ${t.seed} | ${t.exact_same_conditions}/${t.conditions} | ${t.route_changed}/${t.planned} | ${t.dispatch_clock_changed}/${t.planned} | ${t.same_state_differs_from_exact}/${t.informative_decisions} |`).join('\n');
const off=a.ablations.filter(x=>x.kind==='FEEDBACK_OFF').map(x=>`| ${x.policy} | ${signed(x.mean_total_delta_J_proxy)} | ${signed(x.mean_AP_delta_c)} | ${x.total_on_time_delta} | ${x.total_urgent_delta} |`).join('\n');
const mismatch=a.ablations.find(x=>x.kind==='COST_MISMATCH');
const goalTable=g.goals.map(x=>`| ${x.policy} | ${x.original_joint_goal_pass_conditions}/${x.conditions} |`).join('\n');
const report=`# 3·4·5 통합 보완 결과 — 가설 모형·학습·독립 검산 완료

새640예약 중 **602 START=602 COMPLETE/FAIL0**, 3seed×128학습·seed별64 PPO갱신을 마쳤다. DEV에서 seed${sel.seed}/EP${sel.episode}를 선정했고,3seed 모두 새12조건에서 평가했다. 아래 수치는 **새 열·전력 가설 안의 PC 계산**이며 A24 실측 에너지나 실기기 성능 우위가 아니다. 옛 모형과 평가창이 달라 예전0.2%와 새 정책 범위의 차이를 직접적인 개선율로 계산하지 않는다.

## 무엇을 보완했나

3번은 전력→RC온도→실행 중 남은 작업 진행률/전력의 닫힌 고리다. SERIAL 작업 벡터와 완료된 단계 시각은 바꾸지 않는다.4번은 고정ATC 행동 logit0, NN 전체 행동 logit, 현재 온도·공유 활성 이력·명목 후속 비용 입력,3seed 새학습이다.5번은 실제/명목/보상/최종평가의 같은 dynamics.advance_jobs와 목표식이다. CPU/GPU 각1·최대2·비선점AVAILABLE 해제를 유지했다.

명목 예측은 현재 ready후보/관측owner와 과거 pool의 명목 벡터만 쓰며 미래 실제 작업량·도착은 보지 않는다. 같은 식이 미래 예측의 정확함을 보장하지는 않는다. 실제 샘플 변동·명목 overrun·후보 밖 큐·미래 도착은 오차로 남는다.

## 모든 정책 결과

12조건은 분류 비율25/50/75%·두 도착 패턴·초기 열 proxy26/39℃를 사용한다. 각 정책의 같은 조건·입력·잠재 작업량 키를 맞췄다. 비용과 AP는 조건별 평균, 정시·미응답은 전체 예정 요청을 분모로 합산했다. 에너지 창은35초부터 공통 drain끝, 평균AP 창은35초부터 공통 service끝이다. 모든 정책에 같은50ms admission 모음을 적용했다.

${header}
${table}

비학습5정책의 평균 총비용 범위는${fixed(g.non_neural_range.mean_total_J_proxy.min)}~${fixed(g.non_neural_range.mean_total_J_proxy.max)}J*(${fixed(g.non_neural_range.mean_total_J_proxy.range_percent_of_min)}%)다. NN3seed를 포함한8정책 범위는${fixed(g.all_policy_range.mean_total_J_proxy.min)}~${fixed(g.all_policy_range.mean_total_J_proxy.max)}J*(${fixed(g.all_policy_range.mean_total_J_proxy.range_percent_of_min)}%)다. 큰 범위가 열·에너지·납기의 동시 개선이나 NN 우위를 뜻하지 않으므로 비학습 정책 범위와 NN seed범위를 나누어 보고한다.

![전체정책/열조건/납기/NN기여](POLICY_COMPARISON.png)

## 3번: 온도 피드백 대조

같은 고정 정책과 입력에서 강도0은 온도가 진행률·전력에 되돌아가지 않게 한다. 아래는 **피드백0−기본1** 차이다. 음의 소비는 피드백을 끈 쪽 소비가 더 작다는 뜻이며 항상 열 피드백이 에너지를 낮춘다고 가정하지 않았다.

| 정책 | 평균 총비용 ΔJ* | 평균 열 proxy Δ℃ | 전체 정시 Δ | 긴급 정시 Δ |
|---|---:|---:|---:|---:|
${off}

강도0.5/1.5와 시간격자0.1→0.05초도 선정 NN을 재학습하지 않고 같은 입력에 적용했다. 모든 조건별 차이는 ANALYSIS.json의 ablations/timestep에 있다. 단계 진행은 현재 온도의 실제 과거 적분에 반응하고, 이미 완료한 시간을 소급해 바꾸지 않는다. 표본/가정 범위 밖의 실기기 인과 효과는 미검증이다.

## 4번: NN의 실제 기여

${nn}

EXACT는 같은 후보·물리 제약에서 NN 없이 명목 후속 목표식을 최소화하는 대조다. 별도로 NN 초기 actor출력이0이므로 초기 argmax는 같은 모음 규칙의 EDF·CPU우선과 같다. 저장 ${choices.checks}개 공개 판단에서 canonical 첫 행동을 검산했다. 실제 갱신 횟수는 seed별64, Adam_steps는 ${a.curves.map(x=>x.seed+':'+x.Adam_steps).join('/')}다. 학습 실행·행동 변화와 성능 우위를 구분하며 학습 횟수만으로 충분한 수렴을 선언하지 않는다.

DEV선정 적격 flag=${sel.qualification}. 이는 사전 DEV의 미응답/EDF정시 손해 기준이며 모든 긴급 서비스·프로젝트 원목표의 통과를 뜻하지 않는다.3seed별 결과와 학습 곡선은 모두 저장했다. 강한 비학습 대조보다 열·소비가 낮더라도 납기/미완료가 나빠지면 공동 개선으로 쓰지 않는다.

## 5번: 같은 비용식과 근사식 대조

NN 입력·후보 예측·실제 보상에서 현재 열/활성 이력을 유지한다. ${audit.nominal_candidates_replayed}개 선정 명목 후속을 저장된 공개 입력으로 재생했고, ${audit.NN_actions_replayed}개 새 평가 NN 판단을 정확히 재생했다. 실제 보상5성분의 합과 최종 목표식은 저장검사에서 맞았다.

APPROX는 같은 후속 작업·열/납기 항에서 에너지 항만 명목 점유량×단독 전력으로 바꾼 대조다. **APPROX−EXACT** 평균총비용 ${signed(mismatch.mean_total_delta_J_proxy)}J*, 평균열 proxy ${signed(mismatch.mean_AP_delta_c)}℃, 정시 ${mismatch.total_on_time_delta}, 긴급 ${mismatch.total_urgent_delta}다. 조건별 모든 손해를 포함한다. 근사식과 같은 적분식의 차이가 정책 선택으로 이어지는지를 보는 대조이며 실제 기기의 전력 정확도 검증은 아니다.

## 원 공동목표를 그대로 적용

EDF 대비 같은 조건의 총비용10% 이상 감소·평균열 proxy0.5℃ 이상 감소·전체/긴급정시/응답/AVAILABLE 비악화를 동시에 요구했다. 평가를 본 뒤 기준을 바꾸지 않았다.

| 정책 | 원 공동목표 통과 조건 |
|---|---:|
${goalTable}

온도별 모든 정책 집계, 조건별 Pareto/정시 손해, NN−EXACT/EDF, 강도/격자 민감도는 ANALYSIS.json/GOAL_CHECKS.json/CHOICE_DIAGNOSTICS.json에 있다. WAIT는 복수 요청/실배정 기회의 분모에 넣지 않고 물리ready수와 후보수도 구분했다. 미응답·미완료가 다른 정책의 소비 감소는 같은 완료량의 효율 개선으로 승격하지 않는다.

![사전 고정한 hot C50 clustered96 조건의 일정](FIXED_HOT_CASE_GANTT.png)

위 예시는 결과가 나오기 전에 고정한 FRESH_09다. 유리한 조건을 골라 전체 효과로 일반화한 그림이 아니다.

## 검증·파일·경계

- 순수20계약·원 엔진 독립 진행과 새 피드백0의2쌍 P0 PASS. 기존 SERIAL 작업분포의 재현성/새 가설의 소프트웨어 검증이며 실기기 정확도는 아니다.
- 독립 저장검사 ${audit.checks}개(전력/RC 보존/작업량/NN/옵티마이저), 별도 전요청 지표검사 ${metricAudit.checks}개, NN/EXACT 명목후속 재생 ${audit.nominal_candidates_replayed}개 PASS다. 첫 실제 PPO/Adam 갱신3개를 action/shuffle RNG와 Adam전체 moment/step까지 정확히 재생했다. 이는 감사용 재생이며 추가 학습 결과로 세지 않았다.
- 모든 단계의 입력/소스는 OPERATION.json과 후처리 OP들에 SHA로 고정했다. 원사전검사 경로 오류는 환경START0으로 보존했고, 원모형/실패/223회/256회 자료는 변경하지 않았다. 원640 중602소비·잔38, 별도원256잔0/RR잔1, 추적전역예약125478/137712·현재 타host 실제소비 전수값 아님을 유지한다. 추가실행/실패재시작/기기/새열물리fit/주기조회0이다.
- 새 RC시정수25초/저항12/온도기준32℃/진행률floor0.45/누설0.2 등은 명시적 가정이다. 원 SERIAL의 온도 영향은 제거되지 않아 이중 반영 가능성이 있고, 새병행 진행은 독립작업＋열 가정이다. 열 proxy는 CPU 접합 온도나 Android trip point가 아니다. 같은 비용창의 기저는 유지했다.
- 제어·명목 예측·NN추론 단말 오버헤드는 공통 ideal-zero다. 수치 전이는 최대0.1초와 단계 경계에서 갱신하며 peak는 이 적분 경계의 표본 최대다. 시간격자 대조를 별도 저장했다. 통계 CI·실측J·실기기 NN 배포/우위는 미검증이다.
- RESULT/COMPLETE/receipts.jsonl, RAW/준비prediction/NN frames, 모든 UPDATE와 초기/EP2/16배수 체크포인트의 network/Adam/RNG를 이 폴더에 보존한다. SOURCE의 새 엔진은 experiments/coupled_345_20261017이며 원 대화형UI 기본정책은 교체하지 않았다.

원 실행 source 등록은5ea9ed2, 후처리 소스/정의는 평가 전에 추가 등록했다. 최종 handoff proof는 FINAL_HANDOFF_PROOF.json이며 source/input/result/그림/문서의 파일별 SHA로 연결한다. 완료된 operation은 그대로 다시 실행하지 않는다.
`;
fs.writeFileSync(path.join(out,'REPORT.md'),report,{flag:'wx'});
const reportRel='results/COUPLED_345_20261017_01/REPORT.md';
let design=fs.readFileSync(path.join(root,'docs/COUPLED_345.md'),'utf8');
design=design.replace(/^진행 기록:.*$/m,`**602실행·3seed학습·독립검산 완료.** [모든 결과와 한계](../${reportRel})를 정본으로 읽는다. 소스/가정/등록의 이력은 아래에 보존한다.`);
design=design.replace('현재 문서는 **구현/등록 단계**이며 실제602완료·학습 효과·정책 개선을 아직 주장하지 않는다.','실제602완료·학습 기여·모든 손해의 최종 판정은 위 결과 정본을 따른다.');
fs.writeFileSync(path.join(root,'docs/COUPLED_345.md'),design);
let readme=fs.readFileSync(path.join(root,'README.md'),'utf8');
readme=readme.replace(/^\*\*3·4·5.*(?:\r?\n){2}/,`**3·4·5 통합 보완 완료:** [열 피드백·새3seed NN·공통 비용식의 전체 결과](${reportRel}). 새602회 정상·20계약·독립 전력/RC/NN/Adam/전요청 검산을 마쳤습니다. 새 가정 안의 정책 격차와 납기 손해를 함께 보고하며 실측J/실기기 우위는 미검증입니다. 완료 operation은 재시작하지 마세요.\n\n`);
fs.writeFileSync(path.join(root,'README.md'),readme);
const contFile=path.join(root,'CONTINUE.json'),prior=read(contFile);delete prior.coupled_345_development;
const current={status:'COMPLETED_HYPOTHESIS_MODEL_LEARNING_AND_SAVED_AUDIT',report:reportRel,operation:'experiments/coupled_345_20261017/OPERATION.json',
 output:op.output_dir,new_START:602,new_COMPLETE:602,new_FAIL:0,new_reservation:640,remaining_38_unallocated_to_more_runs:true,
 TRAIN:384,PPO_updates_per_seed:64,learner_seeds:op.learner_seeds,selected:sel,
 all_seed_results_preserved:true,core_saved_checks:audit.checks,independent_metric_checks:metricAudit.checks,pure_contract_tests:20,
 no_fixed_ATC_action_logit:true,same_dynamics_for_prediction_reward_and_evaluation:true,
 original_RL256_remaining:0,separate_RR1_untouched:true,physical_accuracy_verified:false,measured_J:null,
 model:'explicit thermal/DVFS/leak hypotheses; not measured A24 parameters',
 original_UI_and_models_preserved:true,automatic_new_runs:false};
fs.writeFileSync(contFile,JSON.stringify({coupled_345_development:current,...prior},null,2)+'\n');
const selectedTrajectory=a.trajectories.find(t=>t.seed===sel.seed),selectedVersusExact=a.versusExact.find(t=>t.seed===sel.seed);
const statusFile=path.join(repo,'docs/PROJECT_STATUS.md'),status=fs.readFileSync(statusFile,'utf8');
const boundary=status.indexOf('## 2026-10-17 A24 2번 비용 보완');
if(boundary<0)throw Error('Unexpected STATUS layout');
const prefix=`## 2026-10-17 A24 3·4·5 통합 보완 — 602완료·3seed/독립검산 완료\n\n[전체 결과·모든 손해](../a24_simulator/${reportRel}): 열→진행/전력→열 가설, 고정ATC logit0의 새3seed PPO, 실제/명목/보상 공통 적분을 구현했다.602START/602완료/FAIL0·384학습·seed별64업데이트, 순수20/독립${audit.checks}/전요청${metricAudit.checks}검사 PASS다. DEV선정${selected}/EP${sel.episode}, EXACT와${selectedTrajectory.exact_same_conditions}/12일정동일·자원${selectedTrajectory.route_changed}/${selectedTrajectory.planned}변경, 평균총비용차${signed(selectedVersusExact.mean_total_delta_J_proxy)}J*/AP${signed(selectedVersusExact.mean_AP_delta_c)}℃·정시Δ${selectedVersusExact.total_on_time_delta}다. 모든3seed·원10%/.5℃·납기비악화 목표와 민감도를 보고한다.\n\n새640중602소비/잔38(자동추가0), 원256잔0/RR잔1별도·추적예약125478/137712 snapshot이다. 원코드/자료/실패/기본UI 보존·기기/새물리fit0이다. 새온도/DVFS/누설은A24식별값이아니며 같은식이 미래예측정확도나 물리우위를 뜻하지 않는다. 완료등록 재실행0, 후속실기기식별/목적식 조정은별도범위다. 검증source5ea9ed2＋후처리SHA핀,최종파일별증거는handoff proof를따른다.\n\n`;
fs.writeFileSync(statusFile,prefix+status.slice(boundary));
const planFile=path.join(repo,'docs/PROJECT_PLAN.md');let plan=fs.readFileSync(planFile,'utf8');
plan=plan.replace('현재 실제602완료·학습우위는 미판정이며 terminal/감사 후 정리한다.',`602완료와 독립저장검산을 마쳤으며 [모든 결과/목표 판정](../a24_simulator/${reportRel})을 따른다. 실제 A24 물리우위는 미검증이다.`);fs.writeFileSync(planFile,plan);
const decisionsFile=path.join(repo,'docs/DECISIONS.md');let decisions=fs.readFileSync(decisionsFile,'utf8');
decisions=decisions.replace('## 2026-10-17 COUPLED-345 — 사용자 지시의 가설 확장·검증 채택',`## 2026-10-17 COUPLED-345 — 가설 확장·602실행·독립검산 완료\n\n[최종 모든 결과/한계](../a24_simulator/${reportRel}):3seed를 모두 보고했고 물리우위·수렴·우수성을 자동 선언하지 않는다. 원목표와 전체손해 판정을 보존한다.`);fs.writeFileSync(decisionsFile,decisions);
const files=fs.readdirSync(out).map(f=>path.join(out,f));
files.push(...fs.readdirSync(__dirname).filter(f=>fs.statSync(path.join(__dirname,f)).isFile()).map(f=>path.join(__dirname,f)),
 path.join(root,'CONTINUE.json'),path.join(root,'README.md'),path.join(root,'docs/COUPLED_345.md'),statusFile,planFile,decisionsFile);
const proof={schema:'A24-coupled345-final-handoff-v1',utc:new Date().toISOString(),
 verification_source_commit:'5ea9ed2',publication_base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),
 final_documents_and_artifacts_uncommitted_at_capture:true,
 new_START:602,new_COMPLETE:602,new_FAIL:0,cap:640,remaining:38,old_RL256_remaining:0,RR_remaining:1,
 physical_accuracy_verified:false,measured_J:null,files:files.map(pin)};
fs.writeFileSync(path.join(out,'FINAL_HANDOFF_PROOF.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:'FINALIZED',files:files.length,selected,source5ea9ed2:true,report:reportRel,core_checks:audit.checks,metric_checks:metricAudit.checks}));
