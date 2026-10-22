'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process');
const R=path.resolve(__dirname,'../S26-D1Check'),S=path.join(R,'s26_simulator'),doc='experiments/plain_edf_v1/RL_DECISION_CONTRACT_KO.md';
const summary=`2026-10-18 후속RL 설계 수정: 사용자 지시로 예측 납기 기반 후보제거·임박요청 강제·ATC선두 확정·NN 뒤 규칙 덮어쓰기를 빼고 **RL이 최종 행동을 선택**한다. 슬롯/지원경로/비선점/실제AVAILABLE 등 물리제약은 유지하고 납기 위험은 입력·학습목적·DEV선정에 반영한다. [설계 계약](${doc}). 이전 ‘RL에 명시적 납기 보호 결합’ 제안을 대체한다. 설계 변경만 완료했으며 S26 새NN/학습/실제 무보호RL 성과는 아직 없다. 단순EDF 주 비교군·원 비교군/기록보존·기존자료만 사용·전력열 정확도gate FAIL·새환경/fit/RL/측정/예약0을 유지한다.`;
for(const [file,title] of [['s26_simulator/STATUS.md','# S26 현재 상태'],['s26_simulator/START_HERE.md','# 여기서 S26 작업을 재개한다'],['docs/PROJECT_PLAN.md','# D1Check 프로젝트 수정 실행계획']]){
 const p=path.join(R,file);let s=fs.readFileSync(p,'utf8');if(!s.startsWith(title))throw Error('Missing title '+file);
 const para=file.startsWith('docs/')?summary.replace(`](${doc})`,`](../s26_simulator/${doc})`):summary;
 fs.writeFileSync(p,s.replace(title,title+'\n\n'+para));
}
const p=path.join(R,'docs/PROJECT_STATUS.md');fs.writeFileSync(p,summary.replace(`](${doc})`,`](../s26_simulator/${doc})`)+'\n\n'+fs.readFileSync(p,'utf8'));
fs.appendFileSync(path.join(R,'docs/DECISIONS.md'),'\n\n## 2026-10-18 — 后续RL去除预测纳期强制保护'.replace('后续RL去除预测纳期强制保护','후속 RL의 예측 납기 강제 보호 제거')+'\n\n- 상태: 사용자 방향 채택. 최종 선택권을 RL에 두고 납기 기반 후보제거·임박 요청 강제·ATC선두 고정·NN후 규칙 덮어쓰기와 고정 행동prior를 제거하는 후속 설계다. 기존 보호판/비학습 정책은 원본으로 보존한다.\n- 슬롯/지원경로/도착/비선점/AVAILABLE 물리 mask와 운영 예산은 유지한다. 납기 위험은 입력·학습목적·DEV선정으로 반영하며 구체 보상/가중치와 모델선정 규칙은 새 학습 전에 별도 확정한다. 제거가 성능 개선이나 납기 보장을 뜻하지 않는다.\n- 단순EDF가 주 비교군이다. 보호 유/무 효과를 주장하려면 같은 학습 조건의 별도 대조가 필요하다. 새 S26 RL은 미구현/미학습·실제 보호제거 성과없음, 이번 새환경/fit/RL/측정/예약0이다. 기존자료만 사용·전력열 정확도gate FAIL을 유지한다.\n- 근거: s26_simulator/'+doc+'.\n');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const E=path.join(S,'experiments/plain_edf_v1'),old=JSON.parse(fs.readFileSync(path.join(E,'IMPLEMENTATION_RECEIPT.json'),'utf8'));
for(const f of old.source_pins)if(sha(path.join(E,f.path))!==f.sha256)throw Error('Earlier implementation changed');
const diff=cp.spawnSync('git',['diff','--check'],{cwd:R,encoding:'utf8'});if(diff.status!==0)throw Error('Diff failed '+diff.stderr);
const receipt={schema:'S26_RL_UNPROTECTED_DESIGN_ONLY',utc:new Date().toISOString(),HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:R,encoding:'utf8'}).trim(),working_tree:'UNCOMMITTED_LOCAL_CHANGES',
  contract:{path:doc,sha256:sha(path.join(S,doc))},old_EDF_implementation_pins_unchanged:true,physical_action_constraints_preserved:true,predicted_deadline_hard_guard_in_future_RL:false,
  current_S26_new_RL_implemented:false,new_policy_environments:0,new_fit:0,new_training:0,new_measurements:0,new_environment_reservation:0,
  validation:'Documentation consistency, git diff check, prior pure-EDF source pin equality; no behavioral/training claim'};
fs.writeFileSync(path.join(E,'RL_DESIGN_RECEIPT.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(receipt));
