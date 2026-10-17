'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const d=require('./design.cjs').design();let checks=0;const need=(v,s)=>{checks++;if(!v)throw Error(s);};
need(d.cases.length===20,'Twenty preselected cases');
for(const a of d.cases){need(a.n===a.input.requests.length&&a.n<=3072,'Cap/all arrivals');need(a.service_stop_s-a.supply_stop_s===600&&a.drain_stop_s-a.supply_stop_s===630,'Common fixed clearance allowance');
 for(const q of a.input.requests){need(q.arrival_s>=35&&q.arrival_s<a.supply_stop_s,'Supply window');need(q.deadline_s>q.arrival_s,'Positive relative deadline');}
 if(a.condition.supply_s===60){const b=d.cases.find(x=>x.condition.supply_s===120&&x.condition.pattern===a.condition.pattern&&x.condition.rate_multiplier===a.condition.rate_multiplier);need(JSON.stringify(a.input.requests)===JSON.stringify(b.input.requests.slice(0,a.n)),'Exact duration prefix');need(JSON.stringify(a.common_potential_key)===JSON.stringify(b.common_potential_key),'Latent key excludes duration');need(Math.abs(b.n-2*a.n)<=48,'Proportional count boundary rounding');}
 const peer=d.cases.find(x=>x.condition.supply_s===a.condition.supply_s&&x.condition.pattern===a.condition.pattern&&x.condition.rate_multiplier===1.2);
 for(const [i,q]of a.input.requests.entries()){const b=peer.input.requests[i];need(q.profile===b.profile&&q.priority===b.priority&&Math.abs(q.deadline_s-q.arrival_s-b.deadline_s+b.arrival_s)<1e-7,'Same per-job template/relative deadline across rates');need(Math.abs((q.arrival_s-35)*a.condition.rate_multiplier-(b.arrival_s-35)*1.2)<1e-7,'Rate scaling');}
}
for(const [p,x]of [['INPUTS.json',d],['PURE_TEST_RESULT.json',{status:'PASS',checks,new_environment_START:0,input_sha256:crypto.createHash('sha256').update(JSON.stringify(d,null,2)+'\n').digest('hex'),cases:d.cases.map(c=>({id:c.id,n:c.n}))}]])fs.writeFileSync(path.join(__dirname,p),JSON.stringify(x,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:'PASS',checks,cases:d.cases.map(c=>({id:c.id,n:c.n}))}));
