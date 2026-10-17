'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),save=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'}),f=(x,n=3)=>x==null?'미정의':Number(x).toFixed(n);
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),parent=path.join(root,op.summary_output),data=read(path.join(out,'EVALUATION.json')),diag=read(path.join(out,'DIAGNOSIS.json')),audit=read(path.join(out,'AUDIT.json'));
if(audit.status!=='PASS'||audit.evaluation_sha256!==sha(path.join(out,'EVALUATION.json')))throw Error('Require bound current audit');
const prior=read(path.join(parent,'ALL_ROWS_WITH_REASONS.json')).rows;
const reward=read(path.join(__dirname,'SAVED_REWARD_DIAGNOSIS.json'));
const rows=data.rows.map(r=>{
 const old=prior.find(p=>p.label===r.label);if(old)return old;
 const notes=['보호'+(r.guard_enabled?'ON':'OFF')+', '+(r.neural_head==='NN'?'학습NN':'actor최종층0 동점대조')];
 for(const tier of ['EDF','STRONG']){const target=data.bounds.find(b=>b.case===r.case&&b.tier===tier&&b.kind==='energy').targets,why=[];
  if(r.original.response_missing)why.push('미응답 '+r.original.response_missing);if(r.original.incomplete)why.push('미완료 '+r.original.incomplete);
  if(r.original.on_time<target.on_time)why.push('전체정시 '+r.original.on_time+'<'+target.on_time);if(r.original.urgent_on_time<target.urgent_on_time)why.push('긴급정시 '+r.original.urgent_on_time+'<'+target.urgent_on_time);
  notes.push(tier+':'+(why.length?'선정 제외('+why.join(', ')+')':'납기 적격'));
 }
 notes.push(r.same_work_common_eligible?'온도창 완료 적격':'온도 선정 제외:동결공통창 안에 전부 완료하지 못함');
 if(r.guard_enabled&&r.neural_head==='NN')notes.push('원RL 전체trace/clock/NN입력 정확재현 대조');
 return {...r,remarks:notes};
});
if(rows.length!==152||prior.some(p=>!rows.some(r=>r.label===p.label)))throw Error('Every previous112 and new40 retained');
save(path.join(out,'ALL_ROWS_WITH_REASONS.json'),{rows,all_rows_displayed:true,removed_rows:0});
const pairs=[];for(const cid of [...new Set(rows.map(r=>r.case))])for(const neural of ['NN','ZERO']){
 const on=rows.find(r=>r.label===cid+'_GUARD_ON_'+neural),off=rows.find(r=>r.label===cid+'_GUARD_OFF_'+neural),onD=diag.rows.find(r=>r.label===on.label),offD=diag.rows.find(r=>r.label===off.label);
 pairs.push({case:cid,condition:on.condition,neural,on:on.label,off:off.label,n:on.n,
  on_time_delta_off_minus_on:off.original.on_time-on.original.on_time,urgent_delta_off_minus_on:off.original.urgent_on_time-on.original.urgent_on_time,
  total_saving_percent_off_vs_on:off.completion&&on.completion?100*(1-off.completion.total_J_proxy/on.completion.total_J_proxy):null,
  common_temperature_reduction_off_vs_on:on.common.mean_AP_c-off.common.mean_AP_c,
  full_completion_within_common:on.same_work_common_eligible&&off.same_work_common_eligible,
  wait_on_s:on.original.wait_s,wait_off_s:off.original.wait_s,expanded_deadline_unsafe_WAIT_states:offD.expanded_deadline_unsafe_WAIT_states,
  chosen_deadline_unsafe_WAIT:offD.chosen_deadline_unsafe_WAIT,
  matched_SLA:off.original.on_time>=on.original.on_time&&off.original.urgent_on_time>=on.original.urgent_on_time&&off.original.response_missing===0&&off.original.incomplete===0});
}
const aggregate=[];for(const neural of ['NN','ZERO'])for(const factor of [.5,1,1.5,2,3]){
 const p=pairs.filter(p=>p.neural===neural&&p.condition.rate_multiplier===factor),on=p.map(p=>rows.find(r=>r.label===p.on)),off=p.map(p=>rows.find(r=>r.label===p.off));
 const complete=[...on,...off].every(r=>r.completion!==null);
 aggregate.push({neural,factor,requests:on.reduce((a,r)=>a+r.n,0),on_time_delta:p.reduce((a,p)=>a+p.on_time_delta_off_minus_on,0),urgent_delta:p.reduce((a,p)=>a+p.urgent_delta_off_minus_on,0),
  total_saving_percent_off_vs_on:complete?100*(1-off.reduce((a,r)=>a+r.completion.total_J_proxy,0)/on.reduce((a,r)=>a+r.completion.total_J_proxy,0)):null,completion_energy_defined:complete,
  mean_temperature_reduction_off_vs_on:p.reduce((a,p)=>a+p.common_temperature_reduction_off_vs_on,0)/p.length,all_common_completed:p.every(p=>p.full_completion_within_common),every_case_SLA_nonworse:p.every(p=>p.matched_SLA)});
}
save(path.join(out,'GUARD_SUMMARY.json'),{pairs,aggregate,frozen_ablation_only:true,no_guard_training_not_yet_tested:true,original_penalty_weights:[.5,.5,8,4,30],all_rows:152,removed_rows:0});
const pairTable=pairs.map(p=>`|${p.case}|${p.neural}|${p.on_time_delta_off_minus_on}|${p.urgent_delta_off_minus_on}|${f(p.total_saving_percent_off_vs_on)}|${f(p.common_temperature_reduction_off_vs_on)}|${f(p.wait_on_s)} → ${f(p.wait_off_s)}|${p.expanded_deadline_unsafe_WAIT_states}|${p.chosen_deadline_unsafe_WAIT}|${p.matched_SLA?'대조납기보존':'대조납기 손해'}; ${p.full_completion_within_common?'공통창 완료':'온도우위 선정 제외:공통창 완료 실패'}|`).join('\n');
const diagnosis=diag.rows.map(d=>`|${d.label}|${d.NN_calls}|${d.queue_feature_clipped_calls}|${d.omitted_ready_sum}/${d.total_ready_sum}|${d.expanded_deadline_unsafe_WAIT_states}|${d.chosen_deadline_unsafe_WAIT}|`).join('\n');
const changed=diag.differences.map(d=>`|${d.case}|${d.a} → ${d.b}|${d.route_changed}/${d.requests}|${d.any_route_or_dispatch_changed}/${d.requests}|`).join('\n');
const all=rows.map(r=>`|${r.case}|${r.policy}|${r.source}|${r.original.on_time}/${r.n}|${r.original.urgent_on_time}/${r.original.urgent_planned}|${f(r.original.P95_completed_response_s)}|${r.original.response_missing}/${r.original.incomplete}|${f(r.completion?.duration_s)}|${f(r.completion?.total_J_proxy)}|${f(r.common.mean_AP_c)}|${f(r.original.peak_AP_c)}|${r.remarks.join('; ')}|`).join('\n');
const learned=pairs.filter(p=>p.neural==='NN'),summary={SLA_nonworse:learned.filter(p=>p.matched_SLA).length,common_complete:learned.filter(p=>p.full_completion_within_common).length,
 selected_unsafe_WAIT:learned.reduce((a,p)=>a+p.chosen_deadline_unsafe_WAIT,0),all_joint_10_point5:learned.filter(p=>p.matched_SLA&&p.full_completion_within_common&&p.total_saving_percent_off_vs_on>=10&&p.common_temperature_reduction_off_vs_on>=.5).length};
const text=`# 납기보호만 끈 RL: 고정NN의 2×2 대조

2026-10-18 사용자 추가 요청에 따른40개 native 실행이다. 현재 RL은 원래 NN logits만으로 요청/자원을 결정한다. 강제 납기보호는 긴급요청이 늦어지는 WAIT를 후보에서 빼는 조건이며 그 부분만 해제했다. 원보상 가중치(.5,.5,8,4,30)·납기페널티·후보8·관측·물리·NN체크포인트·도착/납기/잠재를 유지했다. 공통50ms모음과 WAIT12초/선두1.5초는 유지했다.

고정NN은 보호하에서 학습됐으므로 OFF추론 결과를 보호없이학습한RL의 성능으로 바꾸어 말하지 않는다. 다음은 이 대조와 원인에 맞는 보호없는 paired학습/정책 보완이며 별도 유한등록으로 수행한다. 지금 결과는 재학습이 아니다. 최종actor층0은 동점의 첫후보 선택 대조이며 다른encoder/critic은 그대로다.

새40/FAIL0·원10조건 ON_NN 전체물리trace/요청clock/NN입력/후보/예측 정확재현·독립${audit.checks}검사/NN${audit.independent_NN_frames} PASS다. 원잠재은행은engine만 보며actor는원공개명목추정만 본다. 이전결과112개와이번40개를 아래모두표시했고삭제0이다. [절감상한과오프라인일정](../${path.basename(parent)}/REPORT.md)은그대로보존한다. 상한은 임의WAIT까지허용한완화여서보호해제일정도포함하는지검사했다. J*/AP는A24가설모형이며실측기기우위가아니다.

![모든4변형의부하별결과](GUARD_ABLATION.png)

## 보호 OFF−ON의 모든대조

소비는자기마지막AVAILABLE까지의기저＋증분,온도는원3정책의동결공통종료창이다. 그창안에전부완료하지못한결과는수치를남기되열우위선정에서제외한다. 납기손해도같이표시한다. 모든요청정시가아니라ON의전체/긴급정시수를각각보존하는지판정한다. 숫자요약 ${JSON.stringify(summary)}.

|조건|NN|전체정시Δ|긴급정시Δ|소비절감%|평균온도하락℃|WAIT초ON→OFF|보호가막았을WAIT상태수|그WAIT선택수|비고|
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
${pairTable}

## 원인을 구분하는 모든행

새WAIT를허용해도선택하지않으면고정NN의학습선호와새행동분포를봐야한다. 선택하고납기손해가나면기존페널티만으로그손해를막지못한경우다. NN0과다른행동을고르면서열/소비가비슷하면NN이동작하지않는다는주장과구분한다. 큐특징포화/후보밖요청합계를함께남겨장기입력외삽과후보제한을확인한다. 이고정대조만으로수렴이나보호없는재학습의최선을판정하지않는다.

|일정|NN의사결정수|큐특징포화수|후보밖ready합/전체ready합|새로열린불리WAIT상태|불리WAIT선택|
|---|---:|---:|---:|---:|---:|
${diagnosis}

|조건|대조|자원변경요청|자원또는배정시각변경요청|
|---|---|---:|---:|
${changed}

## 실제로 확인한 비용창 차이

현재긴입력의30개저장결과에서 최고온도벌점을뺀 누적열항/에너지항은 ${f(reward.long_summary.ratio_min,9)}～${f(reward.long_summary.ratio_max,9)}였다. RC식에서충분히식는시간까지적분하면열노출량이R×증분에너지에수렴하고,두정규화상수때문에비율은12×.35/3=1.4가된다. 원학습384개단기episode의비율은 ${f(reward.short_training_summary.ratio_min)}～${f(reward.short_training_summary.ratio_max)}로달랐다. 원NN이처음부터정확히중복된열항으로학습됐다고주장하지않는다.

긴입력에서공개후보전망도같은긴drain을써서열항이거의1.4×에너지항이었다. 보고지표인작업공통창평균AP와다르므로, 보호없이재학습만해도이비용창차이는자동해결되지않는다. 후속정책보완에서는작업완료소비/동결작업창열과보상을맞추고같은창완료손해를함께벌점/검증해야한다. 모든30＋384비용행및10전망요약·원자료SHA는 [진단원자료](../../experiments/guard_ablation_20261018_v2/SAVED_REWARD_DIAGNOSIS.json)에남겼다. 계수를회귀해서맞춘값이아니라같은RC식의항등관계다.

## 원112＋새40: 모든152행과비고

출처WITNESS는미래실현작업량을아는원오프라인진단이며온라인RL과구분한다. P0재현용도행을남긴다. 기준EDF/STRONG미달·미완료·온도창실패사유를표시하며평가분모에서요청을삭제하지않는다.

|조건|정책/일정|출처|전체정시|긴급정시|완료응답P95초|미응답/미완료|완료시간초|완료J*|고정공통평균AP℃|최고AP℃|비고|
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
${all}

## 예산과재개

V1은동명rewards import오류로환경START0에서중단·원소스/실패를보존했다. V2는미사용44를이전해40소비/잔4·이번전역신규예약0이다. 원A24추가38과병렬S26추가576을합친알려진예약snapshot은${read(path.join(__dirname,'BUDGET_RESERVATION.json')).known_tracked_global_snapshot_after}/137712이며모든host실시간집계가아니다. 원headroom잔6이전후잔0이다. 기존38/8/4/4/RR1은불변이다. 새학습/fit/단말0·자동재시도0이다. 원32밀도/82headroom/40＋40LP와기존체크포인트는보존한다. 재학습/정책보완은사용자요청에따라별도고정설계/예산/입력으로진행하며이완료op를재실행하지않는다.
`;
fs.writeFileSync(path.join(out,'REPORT.md'),text,{flag:'wx'});
const concise=`납기WAIT보호ON/OFF×학습NN/actor0의40START/40COMPLETE/FAIL0·원10조건정확재현·독립${audit.checks}/NN${audit.independent_NN_frames} PASS. 보호해제NN 대조납기비악화${summary.SLA_nonworse}/10·불리WAIT선택${summary.selected_unsafe_WAIT}·공동10%/.5℃${summary.all_joint_10_point5}/10. 고정NN대조이고보호없는재학습은후속이다. 원112＋새40을모두표시/제외비고/삭제0.`;
for(const [file,title] of [['docs/PROJECT_STATUS.md','납기보호해제 고정NN 대조 완료'],['docs/PROJECT_PLAN.md','납기보호해제 대조 완료·후속원인보완'],['docs/DECISIONS.md','A24-WAIT-GUARD 고정대조 완료']]){const p=path.join(repo,file);fs.writeFileSync(p,`## 2026-10-18 ${title}\n\n${concise}\n\n[모든결과](../a24_simulator/${op.output_dir}/REPORT.md). 새44잔4/원headroom잔0·기존잔여불변·fit/기기0. 다음은보호없이학습효과와확인된정책원인의유한보완이며이번완료op재시작0·검증은OP SHA/최종proof를따른다.\n\n`+fs.readFileSync(p,'utf8'));}
const rm=path.join(root,'README.md');fs.writeFileSync(rm,`**보호해제 고정NN대조:** [전결과](${op.output_dir}/REPORT.md). ${concise}\n\n`+fs.readFileSync(rm,'utf8'));
const ct=path.join(root,'CONTINUE.json');fs.writeFileSync(ct,JSON.stringify({guard_ablation:{status:'COMPLETED_FROZEN_ABLATION_FOLLOWUP_LEARNING_PENDING',operation:'experiments/guard_ablation_20261018_v2/OPERATION.json',report:op.output_dir+'/REPORT.md',new_START:40,summary},...read(ct)},null,2)+'\n');
const files=[...fs.readdirSync(out).map(f=>path.join(out,f)),...fs.readdirSync(__dirname).filter(f=>fs.statSync(path.join(__dirname,f)).isFile()).map(f=>path.join(__dirname,f)),...['docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/README.md','a24_simulator/CONTINUE.json'].map(f=>path.join(repo,f))];
save(path.join(out,'FINAL_HANDOFF_PROOF.json'),{utc:new Date().toISOString(),HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),new_START:40,all_rows:152,removed_rows:0,parent_proof_sha256:sha(path.join(parent,'FINAL_HANDOFF_PROOF.json')),
 files:files.map(p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size}))});
console.log(JSON.stringify({status:'PUBLISHED_FROZEN_ABLATION',summary,aggregate,files:files.length}));
