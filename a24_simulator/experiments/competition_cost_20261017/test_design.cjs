const assert=require('assert'),d=require('./competition_design.cjs');let checks=0;
const ok=(b,m)=>{assert(b,m);checks++;};
const cases=d.generate(20261711);ok(cases.length===12,'12 fixed grid');
for(const c of cases){const a=d.audit(c);ok(a.planned===48,'48');ok(Object.values(a.by_task_priority).every(v=>v.U>0&&v.N>0),'both priorities per task');ok(a.absolute_deadline_order_inversions>0,'deadline inversions');ok(a.near_arrival_different_deadline_pairs>0,'local deadline competition');ok(a.common_work_window_s[1]<=180,'window');ok(c.input.requests.every(q=>q.deadline_s-q.arrival_s>0),'feasible positive budgets');}
ok(JSON.stringify(cases)===JSON.stringify(d.generate(20261711)),'deterministic');
ok(JSON.stringify(cases)!==JSON.stringify(d.generate(20261731)),'different fixed seed');
ok(new Set(cases.map(c=>c.condition.mix)).size===3,'mixes');
ok(new Set(cases.map(c=>c.condition.pattern)).size===2,'patterns');
assert.throws(()=>d.build(.2,'staggered_wave',.65,1));checks++;
assert.throws(()=>d.build(.25,'bad',.65,1));checks++;
ok(d.SPEC.filter_by_policy_result===false,'not selected by policy performance');
console.log(JSON.stringify({status:'PASS_STATIC_INPUT_DESIGN',assertions:checks,new_environment:0,model_fit:0}));
