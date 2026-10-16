"""FIFO, RR, fixed Greedy controls. User forbids EFT in08; no EFT helper."""
import copy,time
from tools import d1_atc_wait_policy as a

ROLES=("FIFO_FIXED","FIFO_READY_FIXED","RR_READY","GREEDY_RESOURCE_FIFO")

GREEDY_AFFINITY={"classification":"CPU","detection":"CPU"}  # benchmarkonly measuredABBA median

def greedy_action(queue,lanes):
    heads={}
    for q in sorted(queue,key=a.tie):heads.setdefault(GREEDY_AFFINITY[q["task"]],q)
    for q in sorted(heads.values(),key=a.tie):
        job=dict(request_id=q["id"],backend=GREEDY_AFFINITY[q["task"]])
        if a.legal(job,queue,lanes):return dict(kind="single",jobs=[job])
    return None

class Controller(a.Controller):
    def __init__(self,frozen,initial,role):
        if role not in ROLES:raise ValueError("unsupportedcontrol")
        super().__init__(frozen,initial,mode=a.RULE);self.role=role;self.public_policy=role;self.cursor=0;self.rule_log=[]
    def on_public_event(self,event):
        super().on_public_event(event)
        if self.role=="RR_READY" and event["event"]=="dispatch_ns":self.cursor=(("CPU","GPU").index(event["backend"])+1)%2
    def __call__(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        began=time.perf_counter();self.validate_public(queue,lanes,now)
        if any(set(q)!=a.PUBLIC_FIELDS for q in queue):raise ValueError("private ticket")
        sig=(tuple(sorted(q["id"] for q in queue)),tuple((b,l["request"]["id"] if l["request"] else None) for b,l in lanes.items()))
        key=now,self.event_seq,sig;out=dict(now_ns=now,selected=None,reason="resource_event_wait",public_policy=self.role)
        if key==self.last_key:return dict(out,reason="duplicate_decision_revision")
        self.last_key=key;ordered=sorted(queue,key=a.tie);selected=None
        if self.role=="GREEDY_RESOURCE_FIFO":
            action=greedy_action(queue,lanes)
            if action and action["kind"]=="single":selected=action["jobs"][0]
        else:
            for q in ordered:
                if self.role=="RR_READY":
                    resources=("CPU","GPU");cyclic=resources[self.cursor:]+resources[:self.cursor]
                    options=[dict(request_id=q["id"],backend=b) for b in cyclic if b in a.p.backends(q)]
                else:options=[dict(request_id=q["id"],backend="GPU" if q["task"]=="classification" else "CPU")]
                options=[j for j in options if a.legal(j,queue,lanes)]
                if options:selected=options[0]
                if selected or self.role=="FIFO_FIXED":break
        if selected:out.update(selected=copy.deepcopy(selected),reason="no_EFT_rule_dispatch",action_kind="single")
        elif queue:
            if not any(l["request"] for l in lanes.values()):raise ValueError("idlecontrolcannotprogress")
            self.stats["wait_selected"]+=1;out.update(action_kind="resource_wait")
            # No predicted finish minimization or guessed resource release.
            # These controls wait for actual AVAILABLE/newarrival public events.
        else:out["reason"]="empty"
        self.rule_log.append(dict(now_ns=now,selected=selected,queue=len(queue),cursor=self.cursor))
        self.times.append(dict(atc_seconds=0.,candidates_seconds=0.,mask_seconds=0.,encode_seconds=0.,inference_seconds=0.,total_seconds=time.perf_counter()-began,queue=len(queue)))
        return out
