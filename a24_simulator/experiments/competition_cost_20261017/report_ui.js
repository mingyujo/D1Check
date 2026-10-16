'use strict';
const $=s=>document.getElementById(s),fmt=(x,n=4)=>x===null||x===undefined?'미검증':Number(x).toFixed(n);
for(const c of D.cases){const o=document.createElement('option');o.value=c.index;o.textContent=c.label;$('condition').append(o);}
for(const [i,c] of I.entries()){const o=document.createElement('option');o.value=i;o.textContent=c.role+' · '+c.label;$('inputSelect').append(o);}
function render(){
 const id=$('condition').value,observer=$('observer').value,cases=id==='all'?D.cases:D.cases.filter(c=>String(c.index)===id),rows=[];
 const avg=(a,k)=>a.some(x=>k(x)===null)?null:a.reduce((s,x)=>s+k(x),0)/a.length;
 for(const policy of ['EDF_CPU_FIRST','ROLLING_ATC_RL_PROTECTED48']){
  const a=cases.map(c=>c.metrics.find(m=>m.policy===policy));
  rows.push({policy,total:avg(a,x=>observer==='old'?x.total_J_proxy:observer==='native'?x.native_current_index.mean_index:x.new_state_cost.total_J_proxy),
   inc:avg(a,x=>observer==='old'?x.increment_J_proxy:observer==='native'?x.native_current_index.increment_baseline_seconds??null:x.new_state_cost.increment_J_proxy),
   base:avg(a,x=>observer==='native'?x.native_current_index.baseline_device_seconds??null:x.new_state_cost.baseline_J_proxy),
   AP:avg(a,x=>x.mean_AP_c),peak:avg(a,x=>x.peak_AP_c),p95:avg(a,x=>x.P95_completed_response_s),
   on:a.reduce((s,x)=>s+x.on_time,0),planned:a.reduce((s,x)=>s+x.planned,0),urgent:a.reduce((s,x)=>s+x.by_priority.U.on_time,0),
   urgentPlanned:a.reduce((s,x)=>s+x.by_priority.U.planned,0),missing:a.reduce((s,x)=>s+x.missing,0)});
 }
 const energy=observer==='native'?['평균 전류 지수','작업 증분(기저초)','기저초']:['총소비 J*','작업 증분 J*','기저 J*'];
 $('thead').innerHTML='<tr>'+['정책',...energy,'평균 AP ℃','AP peak ℃',id==='all'?'조건별 P95 평균 s':'완료 P95 s','정시/전체','긴급 정시','미응답'].map(t=>'<th>'+t+'</th>').join('')+'</tr>';
 $('tbody').innerHTML=rows.map(r=>'<tr>'+['<strong>'+(r.policy==='EDF_CPU_FIRST'?'EDF':'롤링+ATC+RL')+'</strong>',fmt(r.total),fmt(r.inc),fmt(r.base),fmt(r.AP),fmt(r.peak),fmt(r.p95),r.on+'/'+r.planned,r.urgent+'/'+r.urgentPlanned,r.missing].map(v=>'<td>'+v+'</td>').join('')+'</tr>').join('');
 const duration=cases.reduce((s,c)=>s+c.window_s[1]-c.window_s[0],0)/cases.length;
 $('window').textContent=cases.length+'조건 · 각 정책 동일한 입력 기준 작업 구간'+(cases.length===1?' '+cases[0].window_s.map(t=>fmt(t,3)).join('–')+'초':' · 구간 길이 평균 '+fmt(duration,3)+'초 · 에너지/온도는 조건별 평균, 정시 분모는 합계');
 const a=rows[0],b=rows[1];
 if(observer==='native')$('sensitivity').textContent='전류 상대지수는 D_GPU/새 병행 실측 지원 부족으로 모든 비교에서 미검증이야. J나 0으로 치환하지 않아.';
 else{
  const text='RL − EDF: 총 '+fmt(b.total-a.total)+' J*, 작업 증분 '+fmt(b.inc-a.inc)+' J*, AP 평균 '+fmt(b.AP-a.AP)+' ℃. ';
  if(observer==='new'){
   const bounds=[0,1].map(i=>cases.reduce((s,c)=>s+c.delta.shared_state_cost_sensitivity_delta[i],0)/cases.length);
   $('sensitivity').textContent=text+'미측정 상태의 공유 계수 민감도 ΔJ*: ['+bounds.map(v=>fmt(v)).join(', ')+']. 실제 오차/CI가 아니며 구간이 0을 포함하면 비용 우위를 확정하지 않아.';
  }else $('sensitivity').textContent=text+'이전 고정 점유식은 과거 비교를 위한 보존 관측식이야.';
 }
 window.renderedMetrics=rows;window.renderedCaseIndices=cases.map(c=>c.index);
}
function preview(){
 const c=I[+$('inputSelect').value];$('download').disabled=c.role.includes('퇴역');
 $('download').textContent=$('download').disabled?'퇴역 seed · 실행 금지':'입력 JSON 저장';
 $('inputPreview').innerHTML='<table><tr><th>순서</th><th>작업</th><th>우선순위</th><th>도착 s</th><th>기한 s</th></tr>'+c.input.requests.map(q=>'<tr>'+[q.ordinal+1,q.profile,q.priority==='U'?'긴급':'일반',fmt(q.arrival_s,3),fmt(q.deadline_s,3)].map(v=>'<td>'+v+'</td>').join('')+'</tr>').join('')+'</table>';
}
$('condition').addEventListener('change',render);$('observer').addEventListener('change',render);$('inputSelect').addEventListener('change',preview);
$('download').addEventListener('click',()=>{const c=I[+$('inputSelect').value];if(c.role.includes('퇴역'))return;const u=URL.createObjectURL(new Blob([JSON.stringify(c.input,null,2)+'\n'],{type:'application/json'})),a=document.createElement('a');a.href=u;a.download='A24_competition_'+c.input.seed+'_'+c.index+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);});
render();preview();
