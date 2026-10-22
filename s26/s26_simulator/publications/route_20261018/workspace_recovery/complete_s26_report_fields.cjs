'use strict';
const fs=require('node:fs'),path=require('node:path');
const H=path.resolve(__dirname,'../S26-D1Check/s26_simulator/experiments/a24_unprotected_v1'),p=path.join(H,'report.cjs');
if(fs.existsSync(path.join(H,'REPORT_OPERATION.json')))throw Error('Report operation already sealed');
let s=fs.readFileSync(p,'utf8');
function rep(a,b){if(!s.includes(a))throw Error('Missing report text '+a);s=s.replace(a,b);}
rep('|미AVAILABLE|0~끝API-J|','|미AVAILABLE|전체 응답P95초|긴급 응답P95초|0~끝API-J|');
rep("'|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|');","'|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|');");
rep('|${r.unfinished_AVAILABLE}|${fmt(r.full_observation_API_J)}|','|${r.unfinished_AVAILABLE}|${fmt(r.service.all.p95_s)}|${fmt(r.service.urgent.p95_s)}|${fmt(r.full_observation_API_J)}|');
rep('표의 API-J는 기록된35초~관측종료 구간소비이며 완료된 일의 소비로 바꿔 부르지 않는다.','응답P95는 실제 응답한 요청의 도착~응답 시간이며 미응답을 숨기는 전체 성공률로 쓰지 않는다. 0~끝과35~끝 소비를 구분하며 두 값 모두 완료된 일만의 소비로 바꿔 부르지 않는다.');
rep('명목 예측은 관측owner·현재 후보8개만 포함하고','학습 중 공개 명목비용의 보조손실0.05×exp(-update/32)를 썼으며 실행시 logits에 더하는 고정 prior는 없다. 명목 예측은 관측owner·현재 후보8개만 포함하고');
rep('공유CPU 서비스-prefix와 새3자원 간섭은 전이 가정이다.','공유CPU 서비스-prefix와 새3자원 간섭은 전이 가정이다. 열상태는 기존C0의 AP/skin anchor에 맞춰0초 증분상태0으로 시작하며 한초기조건만 관측했다.');
fs.writeFileSync(p,s);
console.log('REPORT_FIELDS_COMPLETE_BEFORE_REPORT_SEAL');
