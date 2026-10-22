'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),m=read(path.join(out,'WORK_METRICS.json')),audit=read(path.join(out,'AUDIT.json')),diag=read(path.join(out,'CHOICE_DIAGNOSIS.json')),thermal=read(path.join(__dirname,'THERMAL_PURE_TEST.json'));
if(audit.result_sha256!==sha(path.join(out,'RESULT.json'))||audit.work_metrics_sha256!==sha(path.join(out,'WORK_METRICS.json')))throw Error('Exact audit binding');
for(const p of [...op.sources,...op.input_pins])if(sha(p.path)!==p.sha256)throw Error('Immutable source/input');
const f=(n,d=3)=>n==null?'미정의':Number(n).toFixed(d),references=Object.fromEntries(m.rows.filter(r=>r.policy==='EDF').map(r=>[r.case,r]));
const delta=m.rows.map(r=>{const b=references[r.case],complete=r.completion!==null&&b.completion!==null;
 const saving=complete?100*(1-r.completion.total_J_proxy/b.completion.total_J_proxy):null,temp=r.common.mean_AP_c-b.common.mean_AP_c;
 const noHarm=complete&&r.original.on_time>=b.original.on_time&&r.original.urgent_on_time>=b.original.urgent_on_time&&r.original.response_missing===0&&r.original.incomplete===0;
 return {case:r.case,policy:r.policy,condition:r.condition,completion_saving_percent:saving,common_saving_percent:100*(1-r.common.total_J_proxy/b.common.total_J_proxy),common_AP_delta_c:temp,
  on_time_delta:r.original.on_time-b.original.on_time,urgent_delta:r.original.urgent_on_time-b.original.urgent_on_time,no_SLA_harm:noHarm,
  descriptive_joint10percent_point5c_and_SLA:noHarm&&saving>=10&&temp<=-.5};});
fs.writeFileSync(path.join(out,'POLICY_DELTAS.json'),JSON.stringify({rows:delta,original_project_goal_unchanged:true},null,2)+'\n',{flag:'wx'});
const summary=m.summary.map(r=>`|${r.rate_multiplier}|${r.policy}|${r.requests}|${f(100*r.on_time/r.requests)}%|${r.urgent_on_time}/${r.urgent_planned}|${f(r.completion_J_proxy_per_request)}|${f(r.completion_saving_percent)}%|${f(r.mean_common_AP_c)}|${f(r.mean_common_AP_delta_c)}|${r.incomplete}|`).join('\n');
const all=m.rows.map(r=>`|${r.condition.rate_multiplier}|${r.condition.pattern}|${r.policy}|${r.n}|${r.original.on_time}|${r.original.urgent_on_time}|${f(r.original.P95_completed_response_s)}|${f(r.completion?.duration_s)}|${f(r.completion_J_proxy_per_request)}|${f(r.common.mean_AP_c)}|${r.queue_peak}|${f(r.post_supply_clearance_s)}|${r.original.response_missing}/${r.original.incomplete}|`).join('\n');
const work=m.rows.map(r=>{const d=delta.find(d=>d.case===r.case&&d.policy===r.policy);return `|${r.condition.rate_multiplier}|${r.condition.pattern}|${r.policy}|${f(r.completion?.total_J_proxy)}|${f(r.completion?.baseline_percent)}%|${f(d.completion_saving_percent)}%|${f(d.common_saving_percent)}%|${f(d.common_AP_delta_c)}|${d.no_SLA_harm}|`;}).join('\n');
const maxPeak=Math.max(...m.rows.map(r=>r.original.peak_AP_c)),joint=delta.filter(r=>r.policy==='RL'&&r.descriptive_joint10percent_point5c_and_SLA).length;
const text=`# A24 작업 밀도 민감도:120초 고정·0.5~3배

공급시간120초를 고정하고 같은48요청 도착파형의 간격만0.5/1/1.5/2/3배 도착률에 맞게 압축했다. 기준과 달리 총시간에 비례해 같은 밀도를 유지한 실험이 아니다. 각요청의 작업/우선순위/상대납기는 그대로다. 종료경계의 일부파형을 잘라 실제요청수는 정확한정수배와 조금 다르며 모든조건을 공개한다.

![민감도](SENSITIVITY.png)

## 조건과 해석

- 두파형:분산staggered_wave(reference.65)와밀집clustered_recovery(reference.95), 분류/탐지 원cycle50:50·긴급25%·초기AP26℃다. 같은 ordinal의 양route잠재작업량/admission지연을 부하수준간 공유하되 실제도착시각만바꾼다. 부분cycle때문에 전체작업/긴급비율은 약간 달라질 수 있다.
- EDF·ATC·기존DEV선정RL3701/EP064를고정했다. 학습/새물리fit/실기기0이다. 원DEV qualification=false를보존하며 장시간/큰queue에맞춰 재학습한RL로 해석하지 않는다. 보호/최대2자원/CPU·GPU각1/비선점/WAIT12초는불변이다.
- 공급종료155초 후 모든부하에같은600초의새배정여유를주고service755/drain785/관측935초를사전에고정했다. 이전 공급+15초계약과 별도세대다. 완료하지못한요청은누락하지않고 완료에너지를null로보고한다. 결과를보고시간을연장해재실행하지않았다.
- 자기완료J*는35초부터마지막AVAILABLE까지의기저+증분소비이며 작업사이유휴/WAIT를포함한다. 완료시간/작업당소비도함께보고한다. 완료후활성tail약.196J*는별도필드·원잔열trace에보존한다. 같은세정책중가장늦은완료까지의공통에너지/AP도보고한다. 자기완료에너지는정책별기간이다르므로동일벽시계폰전체소비와구분한다.
- 작업당소비의부하간감소는기저소비의분산/열/동시점유변화도포함한다. 스케줄러절감은같은부하의EDF대비로만본다. 서로다른부하의절대J*를그대로비교해정책효율이라고하지않는다. 모든요청분모의정시·긴급·완료응답P95·미응답·미완료를공개한다.
- 같은원파형과잠재prefix를공유하는대응분석이며두독립측정replicate나통계CI가아니다. 원단기/장시간결과를선정에쓰거나물리계수를크게바꾸지않았다. J*와AP는미교정열RC/DVFS/누설가설모형의값이다.

## 온도가 끝없이 오르는지

현재식은 T_next=T_idle+(T-T_idle)exp(-dt/tau)+R*P*(1-exp(-dt/tau))의방열항을포함한다. 유휴평형26℃·tau25초·R12·유한증분전력이다. 초기26℃의모든허용active/idle에서 **${f(thermal.refined_invariant_upper_c,6)}℃** 이하라는불변상한을확인했다. 온도자체의clip은추가하지않았다. 누설전력의기존3배상한을쓰지않은저온구간부등식으로도상한이보존돼해당clip이온도를강제로막는결과가아니다.

16개고정task/실행phase조합×1시간·${thermal.fixed_state_transition_checks}전이의순수방정식검사에서평형수렴했다. 이것은완료요청/학습episode나새실측이아니며실제A24최고온도증명도아니다. 이번실제스케줄trace의최고가설AP는${f(maxPeak)}℃였고모든trace가수학상한안에있음을별도검산했다. 계속일한다고60/100℃로누적되는모형이아니다. 부하가변하면평형주변의변동을허용하며같은온도로정확히고정되는것을가정하지않는다.

![같은공통작업창온도](TEMPERATURE.png)

## 두파형집계

에너지절감은각부하의두조건에너지합계대비이며모든정책이완료한경우만정의한다. 온도는같은조건의3정책공통완료창평균을조건평균했다. 음수절감은소비증가다. 공급구간지표와기저비율도WORK_METRICS에모두있다.

|도착률배수|정책|도착합|전체정시율|긴급정시|완료J*/요청|완료절감vsEDF|공통AP℃|AP차vsEDF|미완료|
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
${summary}

## 모든30조건과대기열

queue최대는입장(+1)/배정(-1)사건을재구성했다. 공급후정리시간은마지막AVAILABLE-155초다. 완료응답P95는미응답을대신하지않으며전체도착분모/미완료와함께본다.

|배수|파형|정책|요청|정시|긴급정시|응답P95초|완료창초|완료J*/요청|공통AP℃|queue최대|공급후정리초|미응답/미완료|
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
${all}

## 같은부하에서에너지·열·납기대조

|배수|파형|정책|완료총J*|기저비율|완료절감|공통절감|공통AP차℃|전체/긴급납기비악화+전체완료|
|---:|---|---|---:|---:|---:|---:|---:|---|
${work}

새10조건에서RL의총소비10%·공통AP.5℃·납기비악화/전체완료기술조건은${joint}/10이다. 과거원사전목표/실기기우위/전체최적한계판정으로소급하지않는다. 에너지나온도하나의개선으로다른쪽손해를성공으로바꾸지않았다.

## 검증·파일

32START/32COMPLETE/환경FAIL0(P0 EDF/RL정확2＋10조건×3정책30), 새36예약/잔4·자동추가0이다. 원coupled38/savings8/sustained4/RR1불변이다. 알려진S26공유예약48을포함한직전125838에새36을더한추적125874/137712 snapshot이며모든host의실시간전수집계는아니다.

원모형/source/CP핀·입력간격/상대납기순수계약·P0원요청경로/clock정확재현을확인했다. 독립${audit.checks}검사·저장NN입력${audit.independent_NN_frames}개전수Float64 argmax·CP전체tensor digest PASS다. 산술최대차${audit.max_absolute_error}, admission지연prefix${diag.admission_prefix_checks}개·동일선택경로잠재workprefix${diag.same_route_work_prefix_checks}개일치다. NNlogit의Torch bitwise일치주장이아니라별도계산의선택인덱스대조다. Adam/가중치/양RNG/counter는runtime불변도확인했다.

source/입력/예산은OPERATION.json·원시/NNframe/receipt는같은결과폴더·수학온도증거는experiments/load_density_20261017/THERMAL_PURE_TEST.json·정량은WORK_METRICS/POLICY_DELTAS·파일SHA는FINAL_HANDOFF_PROOF다. PNG와동일SVG를함께저장했다. 실측에너지/기기우위/장시간학습수렴/모든가능정책의최적값은미확인이다.
`;
fs.writeFileSync(path.join(out,'REPORT.md'),text,{flag:'wx'});
const edf=m.summary.find(r=>r.rate_multiplier===3&&r.policy==='EDF'),atc=m.summary.find(r=>r.rate_multiplier===3&&r.policy==='ATC'),rl=m.summary.find(r=>r.rate_multiplier===3&&r.policy==='RL');
const concise=`120초고정·도착률0.5/1/1.5/2/3배의10입력×3정책+정확P02=32실행을완료했다. 3배정시EDF${edf.on_time}/ATC${atc.on_time}/RL${rl.on_time} (${edf.requests}도착), RL완료소비절감${f(rl.completion_saving_percent)}%/공통AP차${f(rl.mean_common_AP_delta_c)}℃·미완료${rl.incomplete}다. 최고가설AP${f(maxPeak)}℃·불변상한${f(thermal.refined_invariant_upper_c)}℃이고실기기상한은아니다.`;
const prepend=(p,t)=>fs.writeFileSync(p,t+'\n\n'+fs.readFileSync(p,'utf8'));
prepend(path.join(repo,'docs/PROJECT_STATUS.md'),`## 2026-10-17 A24 작업 밀도 민감도 — 완료\n\n${concise}\n\n[모든결과/그림](../a24_simulator/${op.output_dir}/REPORT.md). 독립${audit.checks}/NN${audit.independent_NN_frames}·열순수${thermal.fixed_state_transition_checks}검사PASS·새36잔4/기존잔38·8·4·RR1불변·학습/fit/기기0다. 원단기/장시간판정은보존한다. 다음은결과해석/공유이며자동추가0·검증은새OP/source SHA와최종proof를따른다.`);
prepend(path.join(repo,'docs/PROJECT_PLAN.md'),`## 2026-10-17 작업 밀도 민감도 완료\n\n${concise}\n\n공급120초·모든조건공통추가배정600초를사전에고정했다. 원+15초세대와별도이며모든작업완료에너지를비교하고미완료는null이다. 단위작업소비의부하간변화와같은부하에서정책절감을구분한다. [정본](../a24_simulator/${op.output_dir}/REPORT.md).`);
prepend(path.join(repo,'docs/DECISIONS.md'),`## 2026-10-17 A24-DENSITY 완료·열상한 검산\n\n${concise}\n\n온도자체의clip/물리계수변경0이며방열/유한발열에따른가설상한과16고정상태평형수렴을검산했다. 실제기기최고온도인증은아니다. 원목표판정은소급변경하지않으며모든손해는[정본](../a24_simulator/${op.output_dir}/REPORT.md)에보존한다.`);
prepend(path.join(root,'README.md'),`**작업 밀도0.5~3배 민감도 완료:** [모든결과/열상한/그림](${op.output_dir}/REPORT.md). ${concise}`);
const prior=read(path.join(root,'CONTINUE.json'));fs.writeFileSync(path.join(root,'CONTINUE.json'),JSON.stringify({load_density:{status:'COMPLETED',operation:'experiments/load_density_20261017/OPERATION.json',report:op.output_dir+'/REPORT.md',summary:m.summary,new_START:32,new_COMPLETE:32,new_training:0,thermal_upper_c:thermal.refined_invariant_upper_c},...prior},null,2)+'\n');
const docs=['docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/README.md','a24_simulator/CONTINUE.json','a24_simulator/docs/LOAD_DENSITY.md'].map(p=>path.join(repo,p));
const files=[...fs.readdirSync(out).map(f=>path.join(out,f)),...fs.readdirSync(__dirname).map(f=>path.join(__dirname,f)),...docs];
const proof={utc:new Date().toISOString(),command:process.argv,HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),uncommitted_changes:true,
 result_sha256:sha(path.join(out,'RESULT.json')),audit_sha256:sha(path.join(out,'AUDIT.json')),new_START:32,new_COMPLETE:32,
 files:files.map(p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size}))};
fs.writeFileSync(path.join(out,'FINAL_HANDOFF_PROOF.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({status:'PUBLISHED_ARTIFACTS',summary:m.summary,files:files.length,maxAP:maxPeak}));
