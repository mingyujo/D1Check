"""Adapt the preserved C/D request-round-robin to CPU3/GPU1 availability."""
import copy
import importlib.util
from pathlib import Path

VERSION = 'A24_CLASS_RR_CPU3_GPU1_V1'
LEGACY = Path(__file__).resolve().parent.parent / 'rr_20261017/rr_policy.py'
spec = importlib.util.spec_from_file_location('_a24_preserved_class_rr_20261017', LEGACY)
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


class RoundRobin:
    def __init__(self, cpu_slots=3, gpu_slots=1):
        if cpu_slots < 1 or gpu_slots != 1:
            raise ValueError('RR requires positive CPU capacity and one GPU slot')
        self.capacity = dict(CPU=cpu_slots, GPU=gpu_slots)
        self.base = legacy.RoundRobin()
        self.calls = []

    @property
    def turn(self):
        return self.base.turn

    def __call__(self, state):
        counts = {r:sum(o['route'] == r for o in state['owners']) for r in self.capacity}
        if (any(o['route'] not in self.capacity for o in state['owners'])
                or any(counts[r] > self.capacity[r] for r in counts)):
            raise ValueError('Invalid physical resource owners')
        # Legacy RR sees one busy entry per unavailable route. This preserves
        # request selection/turn semantics while admitting every free CPU3 slot.
        view = dict(state, owners=[dict(route=r) for r in self.capacity
                                  if counts[r] == self.capacity[r]])
        before = self.base.turn
        action = self.base(view)
        record = dict(time_ns=state['now_ns'], action=copy.deepcopy(action),
            turn_before=before, turn_after=self.base.turn, owner_counts=counts,
            free_routes=[r for r in self.capacity if counts[r] < self.capacity[r]],
            future_information=False, post_NN_override=False, NN_execution=False, version=VERSION)
        if action['kind'] == 'DISPATCH':
            record.update(selected_task=self.base.trace[-1]['selected_task'],
                          empty_class_skipped=self.base.trace[-1]['empty_class_skipped'])
        self.calls.append(record)
        return action
