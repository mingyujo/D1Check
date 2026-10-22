'use strict';
const fs=require('node:fs'),path=require('node:path'),p=path.resolve(__dirname,'../S26-D1Check/s26_simulator/experiments/a24_policy_repair_v1/report.cjs');let s=fs.readFileSync(p,'utf8');
if(s.includes('seed_median_percent:'))throw Error('Already applied');
function replace(a,b){if(!s.includes(a))throw Error('Missing anchor '+a.slice(0,100));s=s.replace(a,b);}
replace("seed_on_percent:seedPercents,seed_range_percent:","seed_on_percent:seedPercents,seed_median_percent:seedPercents.map(x=>x.on_percent).sort((a,b)=>a-b)[Math.floor(seedPercents.length/2)],seed_range_percent:");
replace("REPAIR_seed_range:get('REPAIR').seed_range_percent,","BASE_seed_median:get('BASE').seed_median_percent,REPAIR_seed_median:get('REPAIR').seed_median_percent,REPAIR_seed_range:get('REPAIR').seed_range_percent,");
replace('기존방식 추가학습 BASE 3seed평균|보완 REPAIR 3seed평균|','기존방식 추가학습 BASE 평균/중앙|보완 REPAIR 평균/중앙|');
replace("${fmt(g.BASE_on_percent)}%|${fmt(g.REPAIR_on_percent)}%|","${fmt(g.BASE_on_percent)}/${fmt(g.BASE_seed_median)}%|${fmt(g.REPAIR_on_percent)}/${fmt(g.REPAIR_seed_median)}%|");
replace('저장80회와 원학습383회 진단 뒤 후보 누락·장시간 관측창 특징의 학습범위 이탈·공유CPU차단을 보완했다. REPAIR는8개 행동대상에 오래된/새 요청과 종류/우선순위를 포함하고,32개 요청/공개작업 기반의 국소horizon을 예측한다. BASE는 기존8개/관측종료 예측을 같은 예산으로 추가학습한 대조다. FROZEN은 원DEV선정 NN271083의 고정가중치다. 모든NN은 같은32특징/27행동 set-PPO이며 고정ATC prior/예측납기mask/critical강제/NN뒤재배정은0이다. 새 단계의 Adam/RNG/pending 초기화는 두 학습방식에 똑같이 적용했다. 원학습/실패/전체CP는 보존한다.',
'저장된 비교 80회와 원 학습 383회를 진단해 후보 누락, 긴 관측창 특징의 학습범위 이탈, 공유 CPU 병목을 확인했다. REPAIR는 종류·우선순위별로 오래된 요청과 새 요청을 8개 행동대상에 포함하고, 최대 32개 대기 요청을 짧은 국소 구간에서 예측하도록 구현했다. CPU 경합 자체와 실제 실행시간은 그대로다. BASE는 기존의 8개 요청·관측 종료까지의 예측을 같은 예산으로 추가 학습한 대조군이다. FROZEN은 이전 개발자료에서 선정한 NN271083의 고정 가중치다. 모든 NN은 같은 32개 특징·27개 행동의 set-PPO를 사용한다. 예측 납기로 행동을 막거나 긴급 요청을 강제로 선택하거나 NN 결정을 규칙으로 덮어쓰지 않는다. 새 단계의 Adam·RNG·미처리 학습자료 초기화는 두 방식에 똑같이 적용했다. 원 학습·실패·체크포인트는 모두 보존했다.');
replace('각 부하는1024건×분류50/75%×2새stream이다.','각 부하는 1,024건 × 분류 비율 50/75% × 새 입력 흐름 2개다. BASE/REPAIR 칸은 3개 seed의 평균/중앙값 순서다.');
fs.writeFileSync(p,s);console.log('Report clarity and registered seed median reporting applied');
