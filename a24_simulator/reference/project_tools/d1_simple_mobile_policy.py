"""Literature-motivated D1Check adaptations, not COSREL/Niagara reproduction."""
import copy
import statistics
import time
from tools import d1_atc_repair_policy as a
from tools import d1_atc_repair_mobile as old
from tools import d1_atc_repair_study as measured

ROLES = ("RR_READY", "GREEDY_RESOURCE_FIFO")


def preferences():
    values, choices = {}, {}
    for task, priority in (("classification", "urgent"), ("detection", "normal")):
        q = dict(task=task, priority=priority)
        for backend in a.p.backends(q):
            pool = measured.POOL[a.p.key(q, backend)]
            values[task+"_"+backend] = dict(n=len(pool), median_occupancy_ns=statistics.median(sum(r["durations_ns"]) for r in pool))
        choices[task] = min(a.p.backends(q), key=lambda b: (values[task+"_"+b]["median_occupancy_ns"], b != "CPU"))
    return dict(preferred=choices, estimates=values, updated_online=False)


class Controller(a.Controller):
    def __init__(self, frozen, initial, role, affinity=None):
        if role not in ROLES:
            raise ValueError("unregistered simple mobile control")
        super().__init__(frozen, initial, mode=a.RULE)
        self.public_policy = role
        self.role = role
        self.affinity = copy.deepcopy(affinity or preferences()["preferred"])
        self.cursor = 0
        self.rule_log = []
        for task, backend in self.affinity.items():
            if backend not in a.p.backends(dict(task=task, priority="urgent" if task == "classification" else "normal")):
                raise ValueError("unsupported frozen affinity")

    def on_public_event(self, event):
        super().on_public_event(event)
        if self.role == "RR_READY" and event["event"] == "dispatch_ns":
            self.cursor = (("CPU", "GPU").index(event["backend"]) + 1) % 2

    def __call__(self, config, queue, lanes, now, settings, thermal_model, current_ap):
        began = time.perf_counter()
        self.validate_public(queue, lanes, now)
        if any(set(q) != a.PUBLIC_FIELDS for q in queue):
            raise ValueError("private request input")
        out = dict(now_ns=now, selected=None, reason="resource_event_wait", public_policy=self.role)
        sig = (tuple(sorted(q["id"] for q in queue)), tuple((b, l["request"]["id"] if l["request"] else None) for b, l in lanes.items()))
        key = now, self.event_seq, sig
        if key == self.last_key:
            return dict(out, reason="duplicate_decision_revision")
        self.last_key = key
        selected = None
        ordered = sorted(queue, key=a.tie)
        if self.role == "RR_READY":
            resources = ("CPU", "GPU")
            cyclic = resources[self.cursor:] + resources[:self.cursor]
            for q in ordered:
                options = [dict(request_id=q["id"], backend=b) for b in cyclic if b in a.p.backends(q)]
                options = [job for job in options if a.legal(job, queue, lanes)]
                if options:
                    selected = options[0]
                    break
        else:
            # Fixed assignment is the task map; within each resource FIFO.
            heads = {}
            for q in ordered:
                heads.setdefault(self.affinity[q["task"]], q)
            for q in sorted(heads.values(), key=a.tie):
                job = dict(request_id=q["id"], backend=self.affinity[q["task"]])
                if a.legal(job, queue, lanes):
                    selected = job
                    break
        if selected:
            out.update(selected=copy.deepcopy(selected), action_kind="single", reason="simple_mobile_dispatch")
        elif queue:
            if not any(l["request"] for l in lanes.values()):
                raise ValueError("idle simple rule cannot progress")
            self.stats["wait_selected"] += 1
            ends = [old.release(l, self.estimates, b, now) for b, l in lanes.items() if l["request"]]
            ends = [v for v in ends if v is not None and v > now]
            out.update(action_kind="resource_wait", **({"wait_until_ns": min(ends)} if ends else {}))
        else:
            out["reason"] = "empty"
        self.rule_log.append(dict(now_ns=now, selected=selected, queue=len(queue), cursor=self.cursor))
        self.times.append(dict(atc_seconds=0., candidates_seconds=0., mask_seconds=0., encode_seconds=0.,
                               inference_seconds=0., total_seconds=time.perf_counter()-began, queue=len(queue)))
        return out
