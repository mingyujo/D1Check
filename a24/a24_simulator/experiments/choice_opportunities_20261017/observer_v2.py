"""One existing 50ms WAIT to coalesce ready admissions; frozen protection stays."""
import numpy as np
from observer import Observer

class CoalescingObserver(Observer):
    def __init__(self,*args):
        super().__init__(*args);self.coalescing_events=[]

    def choose(self,bank,now,collect=False):
        mode=self.mode
        if mode!='COALESCED_COST':return super().choose(bank,now,collect)
        self.mode='COST_PRIOR'
        try:idx=super().choose(bank,now,collect)
        finally:self.mode=mode
        physical=bank['physical_mask'];slots={int(i)//3 for i in np.flatnonzero(physical[:72])}
        both=bool(physical[:72:3].any() and physical[1:72:3].any())
        if both and len(slots)==1 and bank['mask'][72]:
            # The existing mask enforces nominal due-date protection, one WAIT
            # per head, the 12s cap, and the physical CPU/GPU contract.
            self.opportunities.pop()
            self.coalescing_events.append(dict(time_ns=now,wait_ns=50_000_000,
                head_request_id=bank['diagnostic']['head_request_id']))
            return 72
        return idx

    def summary(self):
        return {**super().summary(),'coalescing_WAIT_calls':len(self.coalescing_events),
                'coalescing_WAIT_s':len(self.coalescing_events)*.05}
