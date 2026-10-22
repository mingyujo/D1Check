"""Implement observable event waits and causal route-aware nominal continuation."""
from pathlib import Path
import hashlib,json
W=Path(__file__).resolve().parent.parent;H=W/'S26-D1Check/s26_simulator/experiments/route_event_learning_v1';changes=[]
def edit(name,pairs):
    p=H/name;s=p.read_text(encoding='utf-8');before=hashlib.sha256(p.read_bytes()).hexdigest()
    for a,b in pairs:
        assert s.count(a)==1,(name,a,s.count(a));s=s.replace(a,b)
    p.write_text(s,encoding='utf-8');changes.append(dict(path=name,parent_sha256=before,new_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
edit('source/multi_simulator.cjs',[
('this.extra_cpu_core_s=0;', 'this.extra_cpu_core_s=0;this.eventWait=null;'),
('this.max_queue=Math.max(this.max_queue,this.ready.length);', "this.max_queue=Math.max(this.max_queue,this.ready.length);if(this.eventWait&&(this.at!==this.eventWait.at||this.eventWait.owners.some(id=>!this.owners.some(o=>o.ordinal===id))||this.time>=this.config.dispatch_stop_s-1e-9)){this.waitDose+=this.time-this.eventWait.start;this.eventWait.decision.wait_end=this.time;this.eventWait=null;}"),
("if(this.time>=this.waitUntil-1e-9&&this.ready.length", "if(!this.eventWait&&this.time>=this.waitUntil-1e-9&&this.ready.length"),
("if(a.kind==='WAIT'){this.waitDose", "if(a.kind==='WAIT_EVENT'){if(!this.owners.length)throw Error('WAIT_EVENT requires an active owner');this.decisions.push({time:this.time,action:a});this.eventWait={start:this.time,at:this.at,owners:this.owners.map(o=>o.ordinal),decision:this.decisions.at(-1)};continue;}if(a.kind==='WAIT'){this.waitDose"),
("this.selectCPU();for(const [o,g]of this.grants)", "if(this.eventWait){this.waitDose+=this.time-this.eventWait.start;this.eventWait.decision.wait_end=this.time;this.eventWait=null;}this.selectCPU();for(const [o,g]of this.grants)"),
("generation:'S26_ROUTE_ENERGY001_G001'", "generation:'S26_ROUTE_EVENT_LEARNING001_G001'")])
edit('source/nominal_rollout.cjs',[
("const waitUntil=obs.time+(first?.wait_s??0);let firstPending=Boolean(first&&!first.wait_s);", "const waitUntil=obs.time+(first?.wait_s??0),initialOwnerIDs=owners.map(o=>o.ordinal);let waitForEvent=Boolean(first?.wait_event),firstPending=Boolean(first&&!first.wait_s&&!first.wait_event);"),
("const eligible=ready.filter(q=>rc.allowed(q).some(r=>rc.legal(r,owners,obs.capacity)));let chosen=null;", "if(waitForEvent&&initialOwnerIDs.some(id=>!owners.some(o=>o.ordinal===id)))waitForEvent=false;const pref=obs.preferred_routes;const eligible=ready.filter(q=>pref?rc.legal(pref[q.ordinal],owners,obs.capacity):rc.allowed(q).some(r=>rc.legal(r,owners,obs.capacity)));let chosen=null;"),
("else if(time>=waitUntil-1e-10&&eligible.length)", "else if(!waitForEvent&&time>=waitUntil-1e-10&&eligible.length)"),
("routes=rc.allowed(q).filter(r=>rc.legal(r,owners,obs.capacity));", "routes=(pref?[pref[q.ordinal]]:rc.allowed(q)).filter(r=>rc.legal(r,owners,obs.capacity));")])
helper="""
function routeContext(obs){
 if(!state.seenTasks){state.seenTasks=new Set;state.recentTasks=[];state.preferred=new Map;state.classCounter=0;}
 const observed=[...obs.ready,...obs.owners.map(o=>({...o,task:o.task??o.route.split('_')[0]}))].sort(FIFO);
 for(const q of observed)if(!state.seenTasks.has(q.ordinal)){state.seenTasks.add(q.ordinal);state.recentTasks.push(q.task);if(state.recentTasks.length>64)state.recentTasks.shift();}
 const mix=state.recentTasks.length<16?.75:state.recentTasks.filter(t=>t==='classification').length/state.recentTasks.length;
 for(const q of obs.ready.slice().sort(FIFO))if(!state.preferred.has(q.ordinal)){
  let r='detection_CPU';if(q.task==='classification'){r=mix<=.625?'classification_NPU':state.classCounter%4===3?'classification_GPU':'classification_NPU';state.classCounter++;}state.preferred.set(q.ordinal,r);
 }
 return {...obs,preferred_routes:Object.fromEntries(obs.ready.map(q=>[q.ordinal,state.preferred.get(q.ordinal)])),observed_classification_mix:mix};
}
"""
edit('policy.cjs',[
('function select(obs,packet,nom,config){',helper+'\nfunction select(obs,packet,nom,config){'),
('const model=packet.multi.models[config.model];state.calls++;', 'const model=packet.multi.models[config.model];state.calls++;if(state.balance)obs=routeContext(obs);'),
("const k=q.task+'|'+q.priority;", "const k=q.task+'|'+q.priority+(state.balance?'|'+obs.preferred_routes[q.ordinal]:'');"),
("a.kind==='WAIT'?{wait_s:a.wait_s}:{ordinal:a.ordinal,route:a.route}", "a.kind==='WAIT_EVENT'?{wait_event:true}:a.kind==='WAIT'?{wait_s:a.wait_s}:{ordinal:a.ordinal,route:a.route}"),
("Number(a.kind==='WAIT')", "Number(a.kind==='WAIT'||a.kind==='WAIT_EVENT')"),
("if(row.length!==WIDTH", "if(state.balance)row[31]=Number(a.kind==='DISPATCH'&&a.route===obs.preferred_routes[q.ordinal]);if(row.length!==WIDTH")])
p=H/'policy.cjs';s=p.read_text(encoding='utf-8');start=s.index('const head=queue[0];for(const wait_s of');end=s.index('\n if(actions.length>ACTIONS)',start)
old=s[start:end]
new="""const head=queue[0];
 if(state.balance){
  for(const wait_s of [.02,.05])if(obs.time+wait_s<config.dispatch_stop_s)actions.push({kind:'WAIT',wait_s,ordinal:head.ordinal,nom:ranked[0].p,ATC:ranked[0].ATC});
  if(obs.owners.length&&obs.time<config.dispatch_stop_s)actions.push({kind:'WAIT_EVENT',ordinal:head.ordinal,nom:ranked[0].p,ATC:ranked[0].ATC});
 }else{
  for(const wait_s of [.05,.2,.5])if((state.mode==='ENERGY_ONLY'||obs.wait_used_s+wait_s<=12+1e-9&&(state.waitByHead.get(head.ordinal)??0)+wait_s<=1.5+1e-9)&&obs.time+wait_s<config.dispatch_stop_s)actions.push({kind:'WAIT',wait_s,ordinal:head.ordinal,nom:ranked[0].p,ATC:ranked[0].ATC});
 }"""
s=s[:start]+new+s[end:];p.write_text(s,encoding='utf-8')
edit('server.cjs',[("require('../a24_stable_learning_v1/policy.cjs')", "require('../route_energy_v1/policy.cjs')"),("require('../a24_stable_learning_v1/source/multi_simulator.cjs')", "require('../route_energy_v1/source/multi_simulator.cjs')")])
edit('nn_train.py',[
("return logits.masked_fill(~mask,-1e9),self.critic(context)", "return (logits/getattr(self,'temperature',1.)).masked_fill(~mask,-1e9),self.critic(context)"),
("losses=[];kls=[];aux_weight=(.15 if self.balance is not None else .05)*math.exp(-self.updates/32.)", "losses=[];kls=[];aux_weight=0. if self.balance is not None else .05*math.exp(-self.updates/32.)"),
("episodes=self.episodes,updates=self.updates,steps=self.steps,pending=self.pending,logs=self.logs,network_sha256=digest(self.net)", "episodes=self.episodes,updates=self.updates,steps=self.steps,pending=self.pending,logs=self.logs,temperature=getattr(self.net,'temperature',1.),network_sha256=digest(self.net)"),
("self.net.load_state_dict(snapshot['network']);self.optimizer.load_state_dict(snapshot['optimizer'])", "self.net.load_state_dict(snapshot['network']);self.net.temperature=snapshot.get('temperature',1.);self.optimizer.load_state_dict(snapshot['optimizer'])")])
(H/'SOURCE_DERIVATION.json').write_text(json.dumps(changes,indent=2)+'\n',encoding='utf-8')
print('EVENT_WAIT_CAUSAL_PREFERENCES_AND_NOMINAL_CONTINUATION_IMPLEMENTED')
