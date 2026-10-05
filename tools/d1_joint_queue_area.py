"""One causal arrived-queue beam with an extra frozen-model AP-area veto.

Existing beam search/limits and old source remain unchanged. No fitted terms,
future arrivals/service, new temperature target or physical overhead assumption.
"""
import math
from tools import d1_pareto_beam as parent

x = parent.x
P = x.p
LABEL = 'ARRIVED_QUEUE_J_PEAK_AREA_V1'


class Controller(parent.Controller):
    def __init__(self, frozen, initial):
        super().__init__(frozen, initial)
        self.reference_area = None
        self.area_vetoes = 0

    def decide(self, *args, **kwargs):
        self.reference_area = None
        result = super().decide(*args, **kwargs)
        if result['reason'] == parent.POLICY: result['reason'] = LABEL
        return result

    def future_area(self, jobs, now):
        """Common past cancels. Use only current modeled t/h and future plans.

        Exactly global35..180 integer queries/trapezoid weights, clipped above
        the effective idle reference. Never include observed future AP/current.
        """
        ap = self.frozen['ap']; slopes = ap['parameters']['ap_slope_at_30_c_per_s']
        t, h = self.t, self.h; values = {}
        if abs(now-round(now)) < 1e-9 and 35 <= round(now) <= 180: values[round(now)] = t
        for segment in P.segments(jobs, now, 180.):
            a, b = segment['start_s'], segment['end_s']
            label = 'resident_idle' if segment['state'] == 'idle' else segment['state']
            u = slopes[label]-slopes['resident_idle']
            for q in range(max(35, math.ceil(a)), min(180, math.floor(b))+1):
                if q > a:
                    values[q] = P.thermal_step(t, h, u, self.init['reference_c'], ap, q-a)[0]
            t, h = P.thermal_step(t, h, u, self.init['reference_c'], ap, b-a)
        expected = set(range(max(35, math.ceil(now)), 181))
        if set(values) != expected: raise ValueError('incomplete future AP grid')
        return sum((.5 if q in (35, 180) else 1.)*max(0., t-self.init['reference_c']) for q, t in values.items())

    def score(self, jobs, now):
        value = super().score(jobs, now)
        if value is None: return None
        area = self.future_area(jobs, now)
        if self.reference_area is None:
            self.reference_area = area  # First call is unchanged parent EFT continuation.
        elif area > self.reference_area+1e-9:
            self.area_vetoes += 1
            return None
        return dict(value, future_rectified_AP_area_c_s=area)


def simulate(frozen, initial, tickets, scenario):
    controller = Controller(frozen, initial)
    vectors = dict(cells={k: [dict(source_request_id='development_context_'+scenario, durations_ns=v) for _ in range(4)]
        for k, v in P.profile(frozen, scenario).items()})
    # Existing ID is the engine's callback ABI; the public candidate ID/version
    # is LABEL and never pooled with its original beam results.
    result = x.old.engine.simulate(dict(protocol=P.VERSION, cells=P.profile(frozen)), vectors, tickets,
        policy=parent.POLICY, settings=x.settings(), seed=201, decision_provider=controller)
    row, segments, cost = x.outcome(result, initial, frozen)
    row.update(decision_calls=len(result['decisions']), decision_host_total_s=sum(controller.callback_times),
        decision_host_max_ms=1000*max(controller.callback_times, default=0.),
        area_vetoes=controller.area_vetoes,
        local_deviations=sum(d.get('local_deviation', False) for d in result['decisions']),
        wait_actions=sum(d.get('chosen_explicit_delay_s', 0.) > 0 and d['selected'] is None for d in result['decisions']))
    return row, result, controller, segments, cost
