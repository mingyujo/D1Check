'use strict';
const VERSION='DEVICE_COMMON_METHOD_V1',ROUTES=['CPU','GPU','NPU'],TASKS=['C','D'];
const FIFO=(a,b)=>a.ready_s-b.ready_s||a.arrival_s-b.arrival_s||a.ordinal-b.ordinal||a.id.localeCompare(b.id);
const EDF=(a,b)=>a.deadline_s-b.deadline_s||FIFO(a,b);
function validateProfile(p){
 for(const t of TASKS)if(!p.allowed[t]?.length||p.allowed[t].some(r=>!ROUTES.includes(r)))throw Error('Explicit supported task routes required');
 for(const r of ROUTES)if(!Number.isInteger(p.owner_capacity[r])||p.owner_capacity[r]<0)throw Error('Owner capacity');
 if(!Number.isInteger(p.cpu_service_workers)||p.cpu_service_workers<1||!(p.energy_scale>0))throw Error('Separate CPU service capacity and energy scale required');
 if(!p.resource_evidence||!p.response_contract)throw Error('Resource evidence and response boundary required');
 return p;
}
function legal(p,q,r,owners){return p.allowed[q.task].includes(r)&&owners.filter(o=>o.route===r).length<p.owner_capacity[r];}
function validateRequests(qs){const ids=new Set;for(const q of qs){if(ids.has(q.id)||!TASKS.includes(q.task)||!['U','N'].includes(q.priority)||![q.arrival_s,q.ready_s,q.deadline_s].every(Number.isFinite)||q.ready_s<q.arrival_s)throw Error('Invalid public request');ids.add(q.id);}}
function publicRequest(q){return Object.fromEntries(['id','ordinal','task','priority','arrival_s','ready_s','deadline_s'].map(k=>[k,q[k]]));}
function validateSnapshot(p,s){
 validateRequests(s.queue);if(!Number.isFinite(s.time_s)||!Number.isFinite(s.sensor.temperature_c)||!Number.isFinite(s.sensor.ambient_c))throw Error('Finite public state');
 if(s.queue.some(q=>q.ready_s>s.time_s+1e-9||q.arrival_s>s.time_s+1e-9))throw Error('Future ready request');
 const ids=new Set(s.queue.map(q=>q.id));for(const o of s.owners){if(ids.has(o.id)||!p.allowed[o.task]?.includes(o.route)||!Number.isInteger(o.stage)||o.stage<0||!(o.phase_progress_public>=0)||!Number.isFinite(o.ready_s)||o.ready_s>s.time_s+1e-9)throw Error('Invalid public owner');ids.add(o.id);}
 for(const r of ROUTES)if(s.owners.filter(o=>o.route===r).length>p.owner_capacity[r])throw Error('Saved owner state exceeds selected resource scenario');
 return s;
}
module.exports={VERSION,ROUTES,TASKS,FIFO,EDF,validateProfile,validateRequests,validateSnapshot,legal,publicRequest};
