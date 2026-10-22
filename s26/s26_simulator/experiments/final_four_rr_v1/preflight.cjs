
'use strict';const fs=require('fs'),path=require('path'),assert=require('assert'),cp=require('child_process'),crypto=require('crypto'),H=__dirname,read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0;const need=(v,s)=>{checks++;assert(v,s)};const {select}=require('./select.cjs'),tasks=['classification','detection'],order=['GPU','NPU','CPU'];
for(const pin of read(path.join(H,'OPERATION.json')).pins)need(sha(pin.path)===pin.sha256,'Frozen source '+pin.path);
for(const f of fs.readdirSync(H).filter(x=>x.endsWith('.cjs')))cp.execFileSync('node',['--check',path.join(H,f)]);
for(let k=0;k<120;k++)for(let bits=0;bits<8;bits++)for(let cur=0;cur<2;cur++){
 const owners=['CPU','GPU','NPU'].filter((r,i)=>bits&(1<<i)).map((r,i)=>({ordinal:100+i,route:'classification_'+r})),ready=Array.from({length:k%13},(_,i)=>({ordinal:i,task:tasks[(i+k)%2],arrival:(i*7)%5,priority:i%2?'urgent':'normal',deadline:k-i})),obs={time:100,capacity:3,owners,ready},a=select(obs,'RR',order,cur),busy=owners.map(o=>o.route.split('_').at(-1));
 const runnable=ready.flatMap(q=>(q.task==='detection'?['CPU']:order).filter(r=>!busy.includes(r)).map(r=>({q,r})));const candidate=runnable.sort((a,b)=>((tasks.indexOf(a.q.task)-cur+2)%2)-((tasks.indexOf(b.q.task)-cur+2)%2)||a.q.arrival-b.q.arrival||a.q.ordinal-b.q.ordinal||order.indexOf(a.r)-order.indexOf(b.r))[0];
 if(owners.length>=3||!candidate)need(a.kind==='NONE'&&a.rr_next===cur,'Blocked queue skips, no pointer advance on NONE');else need(a.kind==='DISPATCH'&&a.ordinal===candidate.q.ordinal&&a.route===candidate.q.task+'_'+candidate.r&&a.rr_next===1-tasks.indexOf(candidate.q.task),'Independent queue rotation/FIFO/routing');
 const mutated=JSON.parse(JSON.stringify(obs));for(const q of mutated.ready){q.deadline+=1000;q.priority=q.priority==='urgent'?'normal':'urgent';}assert.deepStrictEqual(select(mutated,'RR',order,cur),a);checks++;
}
const P=path.resolve(H,'../final_three_policy_v1');assert.deepStrictEqual(read(path.join(H,'INPUTS.json')).cases,read(path.join(P,'INPUTS.json')).cases);checks++;
for(const f of fs.readdirSync(path.join(H,'source')))need(sha(path.join(H,'source',f))===sha(path.join(P,'source',f)),'Same complete plant and nominal source');for(const f of ['physics.cjs','result.cjs','public_observer.cjs'])need(sha(path.join(H,f))===sha(path.join(P,f)),'Same physics/summary');
need(!/require\s*\(/.test(fs.readFileSync(path.join(H,'select.cjs'),'utf8')),'No forecast/physics/NN imports');
fs.writeFileSync(path.join(H,'PREFLIGHT.json'),JSON.stringify({status:'PASS',checks,new_environment:0,RR:'nonpreemptive classification/detection queue rotation; one dispatch per turn',initial_cursor:0,deadline_priority_invariance:true,plant_byte_identical:true},null,2),{flag:'wx'});console.log('FOUR_RR_PREFLIGHT_PASS',checks);
