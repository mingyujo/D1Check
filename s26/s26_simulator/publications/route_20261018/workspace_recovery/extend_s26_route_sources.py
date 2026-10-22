from pathlib import Path
import hashlib,json
W=Path(__file__).resolve().parent.parent
H=W/'S26-D1Check/s26_simulator/experiments/route_energy_v1'
changes=[]
def edit(name,changeset):
    p=H/name; s=p.read_text(encoding='utf-8'); before=hashlib.sha256(p.read_bytes()).hexdigest()
    for old,new in changeset:
        assert s.count(old)==1,(name,old,s.count(old));s=s.replace(old,new)
    p.write_text(s,encoding='utf-8');changes.append(dict(path=name,parent_sha256=before,new_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))

edit('source/multi_simulator.cjs',[
('this.cpu=null;this.ticket=0;', 'this.cpu=null;this.cpus=new Set;this.grants=new Map;this.extra_cpu_core_s=0;this.cpu_concurrency_trace=[];this.ticket=0;'),
('advance(dt){const p=this.physics,t=this.time,J=p.J,H=p.H;', 'advance(dt){const p=this.physics,t=this.time,J=p.J,H=p.H;if(t>=35){this.extra_cpu_core_s+=dt*Math.max(0,this.cpus.size-1);this.cpu_concurrency_trace.push([t,t+dt,this.cpus.size]);}'),
("selectCPU(){const samePhase=this.cpu&&this.cpu.phase===this._cpuPhase,next=this.model.cpu_service==='none'?this.owners.find(o=>o.phase==='INFER'&&rc.slot(o.route)==='CPU')??null:rc.chooseCPU(this.owners,samePhase?this.cpu:null);if(next!==this.cpu||!samePhase){if(this.cpu&&this._cpuStart!==null&&this.time>this._cpuStart)this.cpu_intervals.push({start:this._cpuStart,end:this.time,ordinal:this.cpu.ordinal,route:this.cpu.route,phase:this._cpuPhase});this.cpu=next;this._cpuStart=next?this.time:null;this._cpuPhase=next?.phase??null;}}",
 "selectCPU(){const K=this.model.cpu_workers??1,eligible=this.owners.filter(rc.needsCPU),retained=[...this.grants].filter(([o,g])=>eligible.includes(o)&&o.phase===g.phase).map(([o])=>o),chosen=retained.concat(eligible.filter(o=>!retained.includes(o)).sort((a,b)=>a.cpu_ticket-b.cpu_ticket||a.ordinal-b.ordinal)).slice(0,K);for(const [o,g]of this.grants){if(!chosen.includes(o)||g.phase!==o.phase){if(this.time>g.start)this.cpu_intervals.push({start:g.start,end:this.time,ordinal:o.ordinal,route:o.route,phase:g.phase});this.grants.delete(o);}}for(const o of chosen)if(!this.grants.has(o))this.grants.set(o,{start:this.time,phase:o.phase});this.cpus=new Set(chosen);this.cpu=chosen[0]??null;}"),
("if(rc.slot(o.route)==='CPU'&&this.cpu!==o)continue;", "if(rc.slot(o.route)==='CPU'&&!this.cpus.has(o))continue;"),
("const blocked=rc.needsCPU(o)&&o!==this.cpu;", "const blocked=rc.needsCPU(o)&&!this.cpus.has(o);"),
("else if(rc.needsCPU(o)&&o!==this.cpu){", "else if(rc.needsCPU(o)&&!this.cpus.has(o)){"),
("this.selectCPU();if(this.cpu&&this._cpuStart!==null&&this.time>this._cpuStart){this.cpu_intervals.push({start:this._cpuStart,end:this.time,ordinal:this.cpu.ordinal,route:this.cpu.route,phase:this._cpuPhase});this._cpuStart=null;}", "this.selectCPU();for(const [o,g]of this.grants)if(this.time>g.start)this.cpu_intervals.push({start:g.start,end:this.time,ordinal:o.ordinal,route:o.route,phase:g.phase});this.grants.clear();"),
("generation:'S26_A24_STABLE_LEARNING001_G001'", "generation:'S26_ROUTE_ENERGY001_G001'"),
("shared_cpu_wait_s:this.actual_cpu_wait,", "shared_cpu_wait_s:this.actual_cpu_wait,extra_cpu_core_s:this.extra_cpu_core_s,cpu_workers:this.model.cpu_workers??1,cpu_concurrency_trace:this.cpu_concurrency_trace,")])

edit('source/nominal_rollout.cjs',[
('ticket=0,cpu=null,cpuPhase=null,calls=0;', 'ticket=0,cpu=null,cpuPhase=null,cpus=new Set,grants=new Map,calls=0;'),
("const same=cpu&&cpu.phase===cpuPhase;cpu=model.cpu_service==='none'?owners.find(x=>x.phase==='INFER'&&rc.slot(x.route)==='CPU')??null:rc.chooseCPU(owners,same?cpu:null);cpuPhase=cpu?.phase;", "const eligibleCPU=owners.filter(rc.needsCPU),retained=[...grants].filter(([o,ph])=>eligibleCPU.includes(o)&&ph===o.phase).map(([o])=>o),chosenCPU=retained.concat(eligibleCPU.filter(o=>!retained.includes(o)).sort((a,b)=>a.cpu_ticket-b.cpu_ticket||a.ordinal-b.ordinal)).slice(0,model.cpu_workers??1);cpus=new Set(chosenCPU);grants=new Map(chosenCPU.map(o=>[o,o.phase]));cpu=chosenCPU[0]??null;cpuPhase=cpu?.phase;"),
("if(rc.slot(o.route)==='CPU'&&o!==cpu)continue;", "if(rc.slot(o.route)==='CPU'&&!cpus.has(o))continue;"),
("(rc.slot(p.route)!=='CPU'||p===cpu)", "(rc.slot(p.route)!=='CPU'||cpus.has(p))"),
("else if(!rc.needsCPU(o)||o===cpu){dt=", "else if(!rc.needsCPU(o)||cpus.has(o)){dt="),
("else if(!rc.needsCPU(o)||o===cpu){o.left", "else if(!rc.needsCPU(o)||cpus.has(o)){o.left")])

edit('server.cjs',[
("let buffer='';", "packet.multi.models.CPU3={...packet.multi.models.CENTRAL,cpu_workers:3};packet.multi.models.CENTRAL.cpu_workers=1;let buffer='';"),
("policy.configure({mode:cmd.mode,variant:cmd.variant,choose:bank=>", "const controller=cmd.parent?require('../a24_stable_learning_v1/policy.cjs'):policy;const Plant=cmd.parent?require('../a24_stable_learning_v1/source/multi_simulator.cjs').MultiSimulator:MultiSimulator;controller.configure({mode:cmd.mode,variant:cmd.variant,balance:cmd.balance,choose:bank=>"),
("sim=new MultiSimulator(packet,", "sim=new Plant(packet,"),
("model:c.model??'CENTRAL'", "model:cmd.model??c.model??'CENTRAL'")])

edit('policy.cjs',[
("const WEIGHTS=[.5,.5,8,4,30],ACTIONS=27", "const WEIGHTS=[.5,.5,8,4,30],ACTIONS=27"),
("scores[i]=f.cost.reduce((s,v,j)=>s+WEIGHTS[j]*v,0);", "const b=state.balance;scores[i]=state.mode==='ENERGY_ONLY'?f.cost[0]:b?f.cost[0]/b.scales[0]+f.cost[1]/b.scales[1]+b.dual[0]*f.cost[2]*b.classFactors[0]+b.dual[1]*f.cost[3]*b.classFactors[1]+3*f.cost[4]:f.cost.reduce((s,v,j)=>s+WEIGHTS[j]*v,0);"),
("const index=state.mode==='EXACT'?", "const index=['EXACT','ENERGY_ONLY'].includes(state.mode)?")])
# The first policy replacement is intentionally an identity assertion to pin ABI.
(H/'SOURCE_DERIVATION.json').write_text(json.dumps(changes,indent=2)+'\n',encoding='utf-8')
print('EXTENDED',len(changes),'sources; parent untouched')
