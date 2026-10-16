"""Separately named ready FIFO/EFT control; historical controls stay unchanged."""
import copy
import time
from tools import d1_atc_repair_policy as a
from tools import d1_atc_repair_mobile as old

ROLE = "FIFO_READY_EFT"


class Controller(a.Controller):
    def __init__(self, frozen, initial):
        super().__init__(frozen, initial, mode=a.RULE)
        self.public_policy = ROLE
        self.rule_log = []

    def __call__(self, config, queue, lanes, now, settings, thermal_model, current_ap):
        began = time.perf_counter()
        self.validate_public(queue, lanes, now)
        if any(set(q) != a.PUBLIC_FIELDS for q in queue):
            raise ValueError("private ticket fields")
        out = dict(now_ns=now, selected=None, reason="resource_event_wait", public_policy=ROLE)
        sig = (tuple(sorted(q["id"] for q in queue)),
               tuple((b, l["request"]["id"] if l["request"] else None) for b, l in lanes.items()))
        key = (now, self.event_seq, sig)
        if key == self.last_key:
            return dict(out, reason="duplicate_decision_revision")
        self.last_key = key
        selected = None
        for q in sorted(queue, key=a.tie):
            options = [dict(request_id=q["id"], backend=b) for b in a.p.backends(q)]
            options = [j for j in options if a.legal(j, queue, lanes)]
            if not options:
                continue
            def route(j):
                ds = a.durations(self.estimates, q, j["backend"])
                return ds is None, ds[0] if ds else 0., j["backend"] != "CPU"
            selected = min(options, key=route)
            break
        if selected:
            self.hold = None
            out.update(selected=copy.deepcopy(selected), reason="oldest_ready_minimum_occupancy", action_kind="single")
        elif queue:
            if not any(l["request"] for l in lanes.values()):
                raise ValueError("idle ready rule cannot progress")
            self.stats["wait_selected"] += 1
            ends = [old.release(l, self.estimates, b, now) for b, l in lanes.items() if l["request"]]
            ends = [v for v in ends if v is not None and v > now]
            out.update(action_kind="resource_wait", **({"wait_until_ns": min(ends)} if ends else {}))
        else:
            out["reason"] = "empty"
        self.rule_log.append(dict(now_ns=now, selected=selected, queue=len(queue)))
        self.times.append(dict(atc_seconds=0., candidates_seconds=0., mask_seconds=0.,
                               encode_seconds=0., inference_seconds=0.,
                               total_seconds=time.perf_counter()-began, queue=len(queue)))
        return out
