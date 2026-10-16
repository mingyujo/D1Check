const assert=require('assert/strict'),d=require('../src/bulk_design.cjs');
let checks=0;const need=x=>{assert(x);checks++};
const cases=d.generate(d.preset('quick'));need(cases.length===12);
for(const c of cases){need(c.input.requests.length===48);for(const task of ['C','D'])for(const p of ['U','N'])need(c.input.requests.some(q=>q.profile.startsWith(task)&&q.priority===p));
 for(const q of c.input.requests){const expected=(q.profile.startsWith('C')?2.2:5)*(q.priority==='U'?.7:1);need(Math.abs(q.deadline_s-q.arrival_s-expected)<2e-8);}
 const arrivalOrder=c.input.requests.map(q=>q.ordinal);const dueOrder=[...c.input.requests].sort((a,b)=>a.deadline_s-b.deadline_s||a.ordinal-b.ordinal).map(q=>q.ordinal);
 need(arrivalOrder.some((x,i)=>x!==dueOrder[i]));
 need(c.input.requests.every(q=>q.arrival_s<180&&q.deadline_s<=210));}
need(new Set(cases.map(c=>c.condition.reference_load)).size===3);
need(d.generate(d.preset('wide')).length===36);
assert.throws(()=>d.generate({...d.preset('wide'),counts:[16,32,48]}));checks++;
console.log(JSON.stringify({status:'PASS',checks,environment_START:0}));
