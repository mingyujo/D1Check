'use strict';
// Saved-only publication. This never creates an environment or fits a model.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const pin=p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size});
const save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx'});
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir);
if(fs.existsSync(path.join(out,'FINAL_HANDOFF_PROOF.json')))throw Error('Publication consumed; preserve it');
const result=read(path.join(out,'RESULT.json')),terminal=read(path.join(out,'COMPLETE.json')),audit=read(path.join(out,'AUDIT.json'));
const a=read(path.join(out,'ANALYSIS.json')),fig=read(path.join(out,'FIGURE.json')),microAudit=read(path.join(out,'MICRO_AUDIT.json'));
if(microAudit.result_sha256!==sha(path.join(out,'RESULT.json')))throw Error('Independent finite-class audit required');
if(result.new_START!==280||result.new_COMPLETE!==280||result.new_FAIL!==0||terminal.result_sha256!==sha(path.join(out,'RESULT.json'))||audit.result_sha256!==terminal.result_sha256||a.source_result_sha256!==terminal.result_sha256||fig.source_analysis_sha256!==sha(path.join(out,'ANALYSIS.json'))||fig.sha256!==sha(path.join(out,fig.path)))throw Error('Exact completed/audited/report/figure chain required');
for(const p of [...op.sources,...op.input_pins,op.retired_registration,op.retired_failure])if(sha(p.path)!==p.sha256)throw Error('Source/input mutation: '+p.path);
const fmt=n=>Number(n).toFixed(4),rel='results/SAVINGS_LIMIT_V2_20261017_01',link='../a24_simulator/'+rel+'/REPORT.md';
const baseline=a.cases.reduce((s,x)=>s+x.baseline,0)/a.cases.length;
const meanWork=a.EDF_mean_total-baseline,lowerWork=a.optimistic_mean_total_lower-baseline;
const prior=read(path.join(root,op.parent_output,'RESULT.json'));
const candidates=[...prior.rows.filter(x=>x.kind==='FRESH'),...result.rows.filter(x=>x.kind==='FULL_WITNESS')];
const joint=a.cases.map(x=>candidates.find(r=>r.label===x.energy_heat_nonworse_saved));
const noDeadlineLower=a.cases.reduce((s,x)=>s+x.baseline+x.independent_thermal_linked_work_lower-1e-6,0)/a.cases.length;
const detail={utc:new Date().toISOString(),mean_EDF_baseline_fraction:baseline/a.EDF_mean_total,
 mean_EDF_work_increment:meanWork,optimistic_work_increment_lower:lowerWork,
 maximum_work_increment_saving_percent:100*(1-lowerWork/meanWork),
 required_work_increment_saving_percent_for_total10:10*a.EDF_mean_total/meanWork,
 maximum_total_saving_without_deadline_or_capacity_constraints_percent:100*(1-noDeadlineLower/a.EDF_mean_total),
 found_energy_AP_nonworse_portfolio_saving_percent:100*(1-joint.reduce((s,x)=>s+x.metrics.total_J_proxy,0)/a.cases.length/a.EDF_mean_total),
 found_energy_best_portfolio_mean_AP_change_c:a.cases.reduce((s,x)=>s+x.best_feasible_metrics.mean_AP_c-x.reference.mean_AP_c,0)/a.cases.length,
 temperature_optimistic_mean_reduction_c:a.cases.reduce((s,x)=>s+x.maximum_AP_reduction_c,0)/a.cases.length,
 upper_percent_min:Math.min(...a.cases.map(x=>x.maximum_total_saving_percent)),upper_percent_max:Math.max(...a.cases.map(x=>x.maximum_total_saving_percent)),
 same_completed_work_and_EDF_count_SLA:true,found_portfolio_is_offline:true,physical_accuracy_verified:false};
save(path.join(out,'INTERPRETATION.json'),detail);
fs.writeFileSync(path.join(out,'INTERPRETATION.md'),`# 한계의 원인과 판정 범위\n\n같은12조건에서 스케줄링이 잘되어도 총소비 절감은 평균 ${fmt(a.maximum_mean_saving_percent)}% 이하다. 이는 실제 최적값 자체가 아니라 미래 정보와 불가능할 수도 있는 유리한 열 상태를 허용한 낙관적 상한이다. 발견한 납기 적격 일정은 ${fmt(a.found_mean_saving_percent)}% 절감을 달성했다. 그 사이의 정확한 최적값은 남아 있다.\n\n기저 소비가 EDF 총소비의 ${fmt(100*detail.mean_EDF_baseline_fraction)}%여서 총10%를 줄이려면 작업증분을 ${fmt(detail.required_work_increment_saving_percent_for_total10)}% 줄여야 한다. 그러나 같은 작업을 모두 끝내는 최소 에너지 하한은 작업증분 절감도 ${fmt(detail.maximum_work_increment_saving_percent)}% 이하로 제한한다. 납기와 자원 구간 제약을 모두 제거한 독립 작업량 하한만 써도 총소비 상한은 ${fmt(detail.maximum_total_saving_without_deadline_or_capacity_constraints_percent)}%다. 따라서 10% 목표에 대한 한계는 현재 NN이나 후보 선택의 약함만으로 설명되지 않는다.\n\n총소비 최소로 찾은 일정 묶음의 평균AP 변화는 ${fmt(detail.found_energy_best_portfolio_mean_AP_change_c)}℃다. 각 조건에서 에너지/AP 모두 EDF 이하인 일정만 고른 묶음의 총소비 절감은 ${fmt(detail.found_energy_AP_nonworse_portfolio_saving_percent)}%다. 모두 사후 조건별 묶음이며 단일 온라인 정책이 아니다.\n\nAP의 별도 낙관적 하한이 허용하는 평균 감소는 ${fmt(detail.temperature_optimistic_mean_reduction_c)}℃다. 이 하한은 느슨해서0.5℃ 목표의 불가능을 확인하지 못했다. 가능하다는 증명도 아니다. 에너지10% 불가능 판정을 온도나 모든 부하/기기/모형으로 넓히지 않는다.\n\n작은4요청 사례의120 list 전수는 그 실행 클래스에서만 최적이다. 실제 전역 최적이 ${fmt(a.found_mean_saving_percent)}% 또는 ${fmt(a.maximum_mean_saving_percent)}%라고 확정하지 않는다.\n`,{flag:'wx'});
const korean=`고정12조건·같은 완료량/EDF 전체·긴급 정시 수에서 평균 총소비 절감은 발견한 적격 일정 묶음 ${fmt(a.found_mean_saving_percent)}% 이상, 낙관적 최대 가능 상한 ${fmt(a.maximum_mean_saving_percent)}% 이하다. 10% 평균 불가능=${a.ten_percent_mean_impossible}·개별 ${a.ten_percent_impossible_cases}/12다. 정확한 최적값과 단일 온라인 정책의 도달 가능성은 미확인이다.`;
const status=`## 2026-10-17 A24 절감 한계 — 280완료·독립검산 완료\n\n[전체 조건·하한·달성량](${link}): ${korean} J*는 coupled345 가설 모형이며 실측J/기기 최적 한계가 아니다. V1 tuple/list 사전 비교 실패는 환경0으로 보존·V2 순수9/AST6·P0정확2·독립${audit.checks}검사 PASS다.\n\n새288 중280소비/잔8·원640잔38/RR잔1 불변·추적예약125766/137712 snapshot이다. 학습/새물리fit/기기0·자동추가0, 검증소스 ddadaca+OP SHA 및 최종 proof를 따른다. 다음은 결과 해석/공유이며 추가 실행은 이번 등록에 없다.\n\n`;
const append=(p,t)=>fs.writeFileSync(p,t+fs.readFileSync(p,'utf8'));
fs.appendFileSync(path.join(out,'REPORT.md'),`\n## 원인 해석과 확인 구간 그림\n\n[기저80.2%·납기/자원 제약을 제거한 상한·공동 개선의 해석](INTERPRETATION.md). 작은 유한 클래스의 독립 검산은 MICRO_AUDIT.json의${microAudit.checks}검사 PASS이며,240계획 중44는 지정 list를 그대로 따라 끝냈고196은 금지 WAIT 필요를 기록해 적격 집합에서 제외했다.\n\n![조건별 실제 절감과 낙관적 상한](HEADROOM.png)\n`);
append(path.join(repo,'docs/PROJECT_STATUS.md'),status);
append(path.join(repo,'docs/PROJECT_PLAN.md'),`## 2026-10-17 절감 한계 진단 완료\n\n${korean} 미래 작업량과 유리한 열 상태를 허용한 필요조건 완화의 하한으로 전체 상한을 구했고, 실제 휴리스틱36/소형240/P0·기준4를 완료했다. [결과](${link})의 작은120 list class 전수 최적은 연속 일정 전체 또는48/96요청의 최적이 아니다. 원래10%/.5℃ 공동목표를 변경하지 않았다.\n\n`);
append(path.join(repo,'docs/DECISIONS.md'),`## 2026-10-17 A24-SAVINGS-LIMIT — 완료 판정\n\n${korean} 에너지/AP 각각의 하한은 별도 완화이므로 동시 달성을 보장하지 않는다. 작은 사례의 list class 최적과 전체 문제의 수학적 상한을 구분했다. [모든 결과](${link})와 원 실패/288예산 이전 기록을 보존하며 실기기/다른 부하의 한계로 일반화하지 않는다.\n\n`);
append(path.join(root,'docs/SAVINGS_LIMIT.md'),`# 절감 한계 진단 완료\n\n${korean}\n\n[조건별 수치·모든 손해·검산](../${rel}/REPORT.md) · [상한/실현 절감 그림](../${rel}/HEADROOM.png). 독립${audit.checks}검사 PASS·280START=280COMPLETE/FAIL0, 사전 V1 실패0환경 보존이다. 아래 사전설계의 '결과 없음'은 등록 시점 이력이며 현재 결과는 위 정본을 따른다.\n\n`);
append(path.join(root,'README.md'),`**절감 한계 진단 완료:** [12조건 상한·실제로 찾은 절감·소형 전수 결과](${rel}/REPORT.md). ${korean}\n\n`);
const contpath=path.join(root,'CONTINUE.json'),c=read(contpath);
c.savings_limit_diagnosis={...c.savings_limit_diagnosis,status:'COMPLETED_BOUNDED_OFFLINE_HEADROOM_DIAGNOSIS',report:rel+'/REPORT.md',analysis:rel+'/ANALYSIS.json',final_proof:rel+'/FINAL_HANDOFF_PROOF.json',new_START:280,new_COMPLETE:280,new_FAIL:0,remaining:8,core_saved_checks:audit.checks,pure_tests:9,found_mean_saving_percent:a.found_mean_saving_percent,maximum_mean_saving_percent:a.maximum_mean_saving_percent,ten_percent_mean_impossible:a.ten_percent_mean_impossible,micro_scope:'all120 specified list plans each on2 mixed4 subsets; not continuous global optimum',automatic_new_runs:false};
fs.writeFileSync(contpath,JSON.stringify(c,null,2)+'\n');
fs.writeFileSync(path.join(out,'README.md'),`# 완료 파일 안내\n\n[REPORT.md](REPORT.md)에12조건 전체 수치, [ANALYSIS.json](ANALYSIS.json)에 적격 일정/각 solver상한/모든 새정책 손해를 보존한다. [HEADROOM.png](HEADROOM.png)는 달성 확인 값과 낙관적 상한을 구분한다. START/COMPLETE·receipts·각 일정 원시 trace·잠재 BANK·BOUND·P0·AUDIT·최종SHA proof가 같은 폴더에 있다.\n\n소스/입력/예산은 ../../experiments/savings_limit_20261017_v2/OPERATION.json에 고정했다. 원 V1 실패는 ../SAVINGS_LIMIT_20261017_01에 보존하며 환경START0다. 새288 중280소비·잔8·원38/RR1불변이다. 완료 등록을 재실행하지 마세요. 모형 조건부J*이며 실기기 에너지 검증이 아니다.\n`,{flag:'wx'});
const walk=d=>fs.readdirSync(d,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(d,e.name)):[path.join(d,e.name)]);
const docs=['docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/README.md','a24_simulator/CONTINUE.json','a24_simulator/docs/SAVINGS_LIMIT.md'].map(p=>path.join(repo,p));
const files=[...walk(out),...walk(__dirname),...docs];
const proof={schema:'A24-savings-limit-final-file-proof-v1',utc:new Date().toISOString(),command:process.argv,HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),uncommitted_changes:!!cp.execFileSync('git',['status','--porcelain'],{cwd:repo,encoding:'utf8'}).trim(),
 registration_sha256:sha(path.join(__dirname,'OPERATION.json')),terminal_sha256:sha(path.join(out,'COMPLETE.json')),files:files.map(pin),
 checks:audit.checks,micro_class_checks:microAudit.checks,new_START:280,new_COMPLETE:280,new_FAIL:0,remaining_8_unallocated:true,prior_failed_namespace_preserved:true,old_602_not_restarted:true,original_source_pins_verified:op.sources.length,original_input_pins_verified:op.input_pins.length,
 doc_scope:'Current documentation is pinned at this publication version; historical coupled345 proof pins its own earlier documentation version. No self-hash.',physical_accuracy_verified:false};
save(path.join(out,'FINAL_HANDOFF_PROOF.json'),proof);
console.log(JSON.stringify({status:'FINALIZED',files:proof.files.length,...detail,found_percent:a.found_mean_saving_percent,upper_percent:a.maximum_mean_saving_percent},null,2));
