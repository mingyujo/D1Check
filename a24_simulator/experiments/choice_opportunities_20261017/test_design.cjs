'use strict';
const assert=require('assert/strict'),{generate}=require('./design.cjs');
const d=generate();assert.deepEqual(d,generate());assert.equal(d.cases.length,12);
for(const pair of [...new Set(d.cases.map(c=>c.pair))]){
 const [a,b]=d.cases.filter(c=>c.pair===pair);assert.equal(a.n,48);assert.equal(b.n,48);
 for(let i=0;i<48;i++){
  const x=a.input.requests[i],y=b.input.requests[i];
  assert.equal(x.profile,y.profile);assert.equal(x.priority,y.priority);
  assert.ok(Math.abs((x.deadline_s-x.arrival_s)-(y.deadline_s-y.arrival_s))<1e-7);
  assert.equal(y.arrival_s,b.input.requests[Math.floor(i/b.packet)*b.packet].arrival_s);
  assert.ok(y.arrival_s<180&&y.deadline_s<=210);
 }
 assert.equal(new Set(b.input.requests.map(q=>q.arrival_s)).size,48/b.packet);
 assert.deepEqual(a.common_potential_key,b.common_potential_key);
}
console.log('PASS: deterministic 6 matched pairs, only arrivals/absolute due shift; original relative deadlines and physical scope preserved');
