'use strict';
const fs=require('node:fs'),path=require('node:path'),H=path.resolve(__dirname,'../S26-D1Check/s26_simulator/experiments/a24_unprotected_v3'),p=path.join(H,'report.cjs');
if(fs.existsSync(path.join(H,'REPORT_OPERATION.json')))throw Error('Report already consumed');let s=fs.readFileSync(p,'utf8');
function rep(a,b){if(!s.includes(a))throw Error('Report text missing '+a);s=s.replace(a,b);}
rep('prework_API_J:raw.physics_J-r.api_J','prework_API_J:raw.physics_J-r.api_J,nominal_forecast_queries:raw.nominal_compute.logical_queries');
rep('policy:name,conditions:rows.length','policy:name,nominal_forecast_queries:sum(rows,r=>r.nominal_forecast_queries),nominal_forecast_numerical_failures:sum(rows,r=>r.nominal_forecast_numerical_failures??0),conditions:rows.length');
rep("'## 모든 EVAL 조건·모든 손해'","'명목 예측의 수치불능/전체 후보예측: '+sums.map(s=>s.policy+' '+s.nominal_forecast_numerical_failures+'/'+s.nominal_forecast_queries).join(', ')+'. 실패예측은 진단으로 남기고 예측비용의 미완료/불확실항을최소1로 표시한다. 행동mask나 강제 대체는 없다. 실제환경의 실패2건과 별개다.', '', '## 모든 EVAL 조건·모든 손해'");
rep('저장/자원/CPU/보상/독립계산','저장된 완료/상속 계산의 자원/CPU/보상/독립계산');
rep('새환경·${audit.request_count','저장 계산·${audit.request_count');
fs.writeFileSync(p,s);console.log('FORECAST_DIAGNOSTICS_IN_UNSEALED_REPORTER');
