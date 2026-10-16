'use strict';
// Show the four actual placement counts; this script never runs a policy.
const originalFourRouteShow=showResults;
showResults=function(data){originalFourRouteShow(data);
 const body=document.getElementById('routeCounts');if(!body)return;
 body.innerHTML=data.rows.map(r=>{const n=r.route_counts||{};return '<tr><td>'+esc(r.label)+'</td>'+['C_CPU','C_GPU','D_CPU','D_GPU'].map(k=>'<td>'+esc(n[k]??'미확인')+'</td>').join('')+'</tr>';}).join('');
 const bits=data.rows.map(r=>r.label+': D_GPU '+(r.route_counts?.D_GPU??'미확인')+'건');
 document.getElementById('routeCountNote').textContent='CPU/GPU 선택 가능 여부와 실제 선택 횟수는 다릅니다. '+bits.join(' / ')+'. FIFO 고정 CG/DC 직렬은 고정 배정 대조군입니다. 다른 정책과 주정책은 두 작업의 CPU/GPU를 모두 후보로 받습니다.';
};
