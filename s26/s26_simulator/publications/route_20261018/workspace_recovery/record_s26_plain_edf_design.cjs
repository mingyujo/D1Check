'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process');
const R=path.resolve(__dirname,'../S26-D1Check'),S=path.join(R,'s26_simulator'),E=path.join(S,'experiments/plain_edf_v1');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const testCommand=['s26_simulator/experiments/plain_edf_v1/test_select.cjs'];
const test=JSON.parse(cp.execFileSync(process.execPath,testCommand,{cwd:R,encoding:'utf8'}));
if(test.status!=='PASS_PLAIN_EDF_SELECTION_CONTRACT'||test.checks!==235)throw Error('Selector contract failed');
const text='2026-10-18 비교설계 수정: 사용자 지시로 **단순 EDF를 전체 방식의 주 비교군**으로 둔다. 기존 공통 롤링 배정+EDF는 ATC 순서 추가효과의 보조 비교로 보존한다. [새 선택기·비교설계](experiments/plain_edf_v1/DESIGN_KO.md)는 구현/순수235검사 PASS이며, 봉인 엔진 연결·새 배치 등록·실제 비교실행은 아직 하지 않았다. 새환경/fit/RL/측정/예약0, 기존 자료만 사용·열/전력 정확도gate FAIL·새RL미연결 상태를 유지한다.';
const pstatus=path.join(R,'docs/PROJECT_STATUS.md');let st=fs.readFileSync(pstatus,'utf8');st=text.replace('(experiments/','(../s26_simulator/experiments/')+'\n\n'+st;
fs.writeFileSync(pstatus,st);
const status=path.join(S,'STATUS.md');st=fs.readFileSync(status,'utf8').replace('# S26 현재 상태','# S26 현재 상태\n\n'+text).replace('HEAD b0b1c7df1775fcae3ba2944ed5df6d800382b4cc+미커밋 후속6계보','HEAD b0b1c7df1775fcae3ba2944ed5df6d800382b4cc+미커밋 후속7계보');
st=st.replace('다음 최대3: (1) 기존 원자료의 CPU 실행/대기·열상태 관측 범위와 식별 가능성 정리, (2) 새 근거 없는 계수 탐색을 반복하기 전에 지원범위/검증실패 판정, (3) 유효한 별도 등록 엔진에서만 새 정책평가.',
 '다음 최대3: (1) 기존자료의 지원범위·전력/열 통합 검증실패 판정, (2) 유효한 새 엔진에 단순EDF/공통롤링EDF/롤링ATC를 연결하고 사전 자원순 민감도·입력·공동예산 등록, (3) 같은 조건에서 전체효과와 ATC 추가효과를 분리해 평가하고 그 뒤 새RL 여부 판단.');
fs.writeFileSync(status,st);
const start=path.join(S,'START_HERE.md');st=fs.readFileSync(start,'utf8').replace('# 여기서 S26 작업을 재개한다','# 여기서 S26 작업을 재개한다\n\n'+text).replace('새6개 실험 snapshot','새7개 실험 snapshot');fs.writeFileSync(start,st);
const plan=path.join(R,'docs/PROJECT_PLAN.md');st=fs.readFileSync(plan,'utf8').replace('# D1Check 프로젝트 수정 실행계획','# D1Check 프로젝트 수정 실행계획\n\n'+text.replace('(experiments/','(../s26_simulator/experiments/')+' 전체효과 비교는 같은 자원·입력·납기·완료량에서 수행한다. CPU우선 순서 하나가 제안정책에 유리한 비교군이 되지 않도록 사전 고정 자원순 민감도를 함께 보고한다. 아래는 이전 단계 이력이다.');fs.writeFileSync(plan,st);
fs.appendFileSync(path.join(R,'docs/DECISIONS.md'),'\n\n## 2026-10-18 — 단순 EDF를 전체 방식의 주 비교군으로 수정\n\n- 상태: 사용자 지시로 비교 목적/주 비교군 변경 채택. 기존 공통 롤링+EDF 결과는 보조 ablation으로 보존하며 단순 EDF 대비 전체 효과라고 인용하지 않는다.\n- 새 plain_edf_v1/select.cjs는 납기→도착→ordinal, 빈 지원 자원의 고정 CPU/GPU/NPU 순서만 사용한다. 실제 AVAILABLE까지 점유·지원범위·동시성은 동일하다. 예상시간/온도/에너지/NN/자발적WAIT0, 순수235검사 PASS다. 생산 엔진 연결·새 배치 등록·새 비교실행은 미완료다.\n- 고정 자원순 민감도를 사전 보고하고 같은 입력/납기/분모/완료량에서 단순EDF·공통롤링EDF·롤링ATC를 구분한다. 전체효과와 순서효과 및 향후 RL효과를 혼합하지 않는다.\n- S26 최근 세대는 새RL 미구현/미학습이다. 방법론만으로는 공동 후보선택·후속 예측·독립NN·공통상태전이를 갖춘 최신 A24 후속 구조가 더 완성됐다는 판단이며, A24 가설 열/스로틀링 계수를 S26 실측 상수로 가져오거나 RL 우위를 승인한 것은 아니다.\n- 새환경/fit/RL/측정/예약0, 기존 자료만 사용·원본/실패/예산보존·전력열 정확도gate FAIL은 유지한다. 근거: s26_simulator/experiments/plain_edf_v1/DESIGN_KO.md.\n');
const receipt={schema:'S26_PLAIN_EDF_SELECTOR_IMPLEMENTATION_ONLY',utc:new Date().toISOString(),HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:R,encoding:'utf8'}).trim(),working_tree:'UNCOMMITTED_LOCAL_CHANGES',
 command:'node '+testCommand[0],node_version:process.version,source_pins:['select.cjs','test_select.cjs','DESIGN_KO.md'].map(n=>({path:n,sha256:sha(path.join(E,n))})),test,
 primary_comparator:'PLAIN_EDF_FIXED_RESOURCE_ORDER',old_rolling_EDF:'SECONDARY_REQUEST_ORDER_ABLATION',integrated_into_production_engine:false,comparison_environments_run:0,new_fit:0,new_RL:0,new_measurements:0,new_environment_reservation:0};
fs.writeFileSync(path.join(E,'IMPLEMENTATION_RECEIPT.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(receipt));
