'use strict';
// Pure policy-contract checks; no simulator instance, measured data fit, or RL.
const assert=require('node:assert/strict'),{select}=require('./select.cjs');let checks=0;
const q=(ordinal,task,deadline,arrival=0)=>({ordinal,task,deadline,arrival});
const obs=(ready,owners=[],capacity=3)=>({time:10,capacity,ready,owners});
const eq=(a,b)=>{assert.deepEqual(a,b);checks++;};
let s=obs([q(2,'classification',3),q(1,'detection',2)]);eq(select(s).ordinal,1);eq(select(s).route,'detection_CPU');
eq(select(obs([q(0,'classification',2)] )).route,'classification_CPU');
// Earliest detection is blocked on CPU; an eligible later classification can use GPU.
s=obs([q(0,'detection',1),q(1,'classification',2)],[{route:'classification_CPU',phase:'POST'}]);
eq(select(s).ordinal,1);eq(select(s).route,'classification_GPU');
eq(select(obs([q(0,'classification',2)],[{route:'detection_CPU'},{route:'classification_GPU'}])).route,'classification_NPU');
eq(select(obs([q(0,'classification',2)],[{route:'detection_CPU'}],1)).kind,'NONE');
eq(select(obs([])).kind,'NONE');
eq(select(obs([q(3,'classification',2,1),q(2,'classification',2,0)])).ordinal,2);
eq(select(obs([q(3,'classification',2),q(2,'classification',2)])).ordinal,2);
// Forecast/model/sensor changes and urgent labels do not affect plain EDF.
s=obs([q(1,'classification',4),q(0,'classification',2)]);const before=JSON.stringify(s),base=select(s);
eq(select({...s,sensor:{AP:1000},model:'HIGH',future_arrivals:[q(8,'detection',0)]}),base);
eq(select({...s,ready:s.ready.map(x=>({...x,priority:x.ordinal?'urgent':'normal'}))}),base);
eq(JSON.stringify(s),before);eq(base.forecast_calls,0);
eq(select(s,['NPU','GPU','CPU']).route,'classification_NPU');
for(const [data,order] of [[obs([q(0,'classification',2,11)]),undefined],[obs([q(0,'unknown',2)]),undefined],[s,['CPU','CPU','NPU']],[obs([],[{route:'detection_CPU'},{route:'classification_CPU'}]),undefined]]){assert.throws(()=>select(data,order));checks++;}
// Enumerate masks and route-order permutations without running an environment.
const orders=[['CPU','GPU','NPU'],['CPU','NPU','GPU'],['GPU','CPU','NPU'],['GPU','NPU','CPU'],['NPU','CPU','GPU'],['NPU','GPU','CPU']];
for(let mask=0;mask<8;mask++)for(let capacity=1;capacity<=3;capacity++)for(const order of orders){
 const held=['CPU','GPU','NPU'].filter((_,j)=>mask&(1<<j)),owners=held.map(r=>({route:'classification_'+r}));
 const ready=[q(0,'detection',1),q(1,'classification',2)],out=select(obs(ready,owners,capacity),order);
 const eligible=ready.filter(x=>(x.task==='detection'?['CPU']:order).some(r=>!held.includes(r)));
 if(held.length>=capacity||!eligible.length)eq(out.kind,'NONE');
 else{eq(out.ordinal,eligible[0].ordinal);eq(out.route,eligible[0].task+'_'+order.find(r=>!held.includes(r)&&(eligible[0].task!=='detection'||r==='CPU')));}
}
console.log(JSON.stringify({status:'PASS_PLAIN_EDF_SELECTION_CONTRACT',checks,simulator_instances:0,new_fit:0,new_training:0}));
