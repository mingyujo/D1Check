'use strict';
const fs=require('fs'),path=require('path'),W=path.resolve(__dirname,'..'),H=path.join(W,'S26-D1Check/s26_simulator/experiments/route_event_learning_v1');
function edit(name,a,b){const p=path.join(H,name);let s=fs.readFileSync(p,'utf8');if(s.split(a).length!==2)throw Error(name+' trace assertion');fs.writeFileSync(p,s.replace(a,b));}
edit('policy.cjs','state.classCounter=0;','state.classCounter=0;state.taskTrace=[];state.preferenceTrace=[];');
edit('policy.cjs','state.seenTasks.add(q.ordinal);state.recentTasks.push(q.task);','state.seenTasks.add(q.ordinal);state.taskTrace.push({ordinal:q.ordinal,task:q.task,time:obs.time});state.recentTasks.push(q.task);');
edit('policy.cjs','state.preferred.set(q.ordinal,r);','state.preferred.set(q.ordinal,r);state.preferenceTrace.push({ordinal:q.ordinal,route:r,time:obs.time,observed_mix:mix,seen_count:state.recentTasks.length,class_counter:state.classCounter});');
edit('policy.cjs','module.exports={select,configure,cacheStats,WIDTH,ACTIONS};',"const contextStats=()=>({task_seen:state?.taskTrace??[],preferences:state?.preferenceTrace??[],scope:'Seen-ready public task metadata only; preference is a feature/nominal continuation, never an actual action mask.'});module.exports={select,configure,cacheStats,contextStats,WIDTH,ACTIONS};");
edit('source/multi_simulator.cjs','policy_route_counts:this.route_counts,','policy_route_counts:this.route_counts,route_context_evidence:actions.contextStats?.()??null,');
console.log('CAUSAL_EVENT_ROUTING_CONTEXT_TRACE_READY');
