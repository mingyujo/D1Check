"""Schedule-sensitive research cost model, not a calibrated A24 energy model.

Preserve observed solo/pair steady powers. Generalize their shared component
to other pairs and allow it to decay during idle. Both generalizations are
explicit hypotheses. No policy outcome is used to select the parameters.
"""
import math

SOLOS = ('classification_CPU', 'classification_GPU', 'detection_CPU', 'detection_GPU')
KNOWN_PAIR = 'classification_GPU+detection_CPU'
DG_ANCHOR = .6013808404579677
SPEC = dict(schema='A24-shared-activation-cost-v1',
    default_shared_scale=1., default_idle_decay_s=.9,
    shared_scale_grid=[0., .5, 1., 1.5], idle_decay_grid_s=[0., .225, .9, 3.6],
    parameter_selection='frozen before saved-policy comparison; no largest-gap selection',
    shared_component='CG + DC - CG_DC; steady solo and measured pair preserved at every scale',
    idle_decay='hypothesis; 0.9s is a scenario reference, not an identified hardware time constant',
    unknown_pair='solo sum minus one shared active component; unvalidated transfer',
    baseline='same fixed window, unchanged reference baseline',
    initial_state='zero at explicit history start unless caller supplies another value',
    temperature_feedback=False, measured_J=None, new_fit=0)


def label(task, route):
    if task not in ('C', 'D') or route not in ('CPU', 'GPU'):
        raise ValueError('Unsupported task/route')
    return ('classification' if task == 'C' else 'detection') + '_' + route


def segments(owners, start, end):
    """Explicit exclusive resource states, including idle and pre-window history."""
    if not math.isfinite(start + end) or end <= start:
        raise ValueError('Finite positive history required')
    edges = {start, end}
    for r in owners:
        a, b = r['start_s'], r['end_s']
        if not math.isfinite(a + b) or b <= a or a < start - 1e-8 or b > end + 1e-8:
            raise ValueError('Invalid or out-of-history owner')
        label(r['task'], r['route'])
        edges.update((max(start, a), min(end, b)))
    edges = sorted(edges)
    out = []
    for a, b in zip(edges, edges[1:]):
        active = [r for r in owners if r['start_s'] < b and r['end_s'] > a]
        if len(active) > 2 or len({r['route'] for r in active}) != len(active):
            raise ValueError('Resource ownership conflict')
        names = tuple(sorted(label(r['task'], r['route']) for r in active))
        if out and out[-1][2] == names and out[-1][1] == a:
            out[-1] = (out[-1][0], b, names)
        else:
            out.append((a, b, names))
    return out


class SharedActivationCost:
    def __init__(self, frozen_model, shared_scale=1., idle_decay_s=.9):
        self.solo = dict(zip(frozen_model['supported_states'], frozen_model['coefficients_W_proxy']))
        self.pair = self.solo.pop(KNOWN_PAIR)
        self.solo['detection_GPU'] = DG_ANCHOR
        self.baseline = frozen_model['reference_baseline_W_proxy']
        self.identified_discount = self.solo['classification_GPU'] + self.solo['detection_CPU'] - self.pair
        if (not frozen_model['adopted_for_qualified_states'] or self.identified_discount < 0
                or any(not math.isfinite(p) or p <= 0 for p in self.solo.values())):
            raise ValueError('Qualified positive steady anchors required')
        if not math.isfinite(shared_scale + idle_decay_s) or shared_scale < 0 or idle_decay_s < 0:
            raise ValueError('Nonnegative finite scenario parameters required')
        self.shared = shared_scale * self.identified_discount
        if self.shared > min(self.solo.values()):
            raise ValueError('Shared component exceeds solo power; negative dynamic power')
        self.scale, self.tau = shared_scale, idle_decay_s

    def observe(self, owners, lo, hi, history_start=0., initial_shared=0.):
        if not history_start <= lo < hi or not 0 <= initial_shared <= 1:
            raise ValueError('Window/history/initial state')
        # Observers may receive a longer saved schedule. Only the supplied
        # past up to hi is used; no owner after hi contributes to this window.
        clipped = [dict(r, end_s=min(r['end_s'], hi)) for r in owners if r['start_s'] < hi]
        seg = segments(clipped, history_start, hi)
        route_s = {s: 0. for s in SOLOS}
        states = {}; tail_s = 0.; q = initial_shared
        for a, b, active in seg:
            left, right = max(lo, a), min(hi, b)
            dt = max(0., right - left)
            if active:
                q = 1.
                for name in active:
                    route_s[name] += dt
                state = '+'.join(active)
                states[state] = states.get(state, 0.) + dt
            else:
                if self.tau:
                    if dt:
                        tail_s += q * math.exp(-(left-a)/self.tau) * self.tau * -math.expm1(-dt/self.tau)
                    q *= math.exp(-(b-a)/self.tau)
                else:
                    q = 0.
        known_overlap = states.get(KNOWN_PAIR, 0.)
        unknown_overlap = sum(t for s, t in states.items() if '+' in s and s != KNOWN_PAIR)
        route_work = sum(self.solo[s] * t for s, t in route_s.items())
        known_credit = -self.identified_discount * known_overlap
        transferred_credit = -self.shared * unknown_overlap
        tail = self.shared * tail_s
        increment = route_work + known_credit + transferred_credit + tail
        if increment < -1e-8:
            raise ValueError('Nonphysical negative increment')
        baseline = self.baseline * (hi-lo)
        unsupported = sorted(s for s, t in states.items() if t and (s == 'detection_GPU' or ('+' in s and s != KNOWN_PAIR)))
        return dict(schema=SPEC['schema'], status='HYPOTHETICAL_SCHEDULE_COST',
            window_s=[lo, hi], baseline_J_proxy=baseline, increment_J_proxy=increment,
            total_J_proxy=baseline+increment, additive_route_J_proxy=route_work,
            identified_pair_credit_J_proxy=known_credit,
            hypothesized_pair_credit_J_proxy=transferred_credit,
            hypothesized_idle_tail_J_proxy=tail,
            route_seconds=route_s, exclusive_state_seconds=states,
            known_pair_overlap_s=known_overlap, transferred_pair_overlap_s=unknown_overlap,
            shared_idle_equivalent_s=tail_s, shared_activation_state=q,
            current_shared_idle_W_proxy=self.shared*q,
            shared_active_W_proxy=self.shared, idle_decay_s=self.tau, shared_scale=self.scale,
            unsupported_states=unsupported, measured_J=None, physical_energy_accuracy_verified=False,
            hypothetical_idle_dynamics=True, hypothetical_unmeasured_pair_transfer=bool(unknown_overlap),
            idle_tau_is_not_sensor_tau_identification=True)

    def episode(self, owners, history_start=0., initial_shared=0.):
        """Full job increment, including analytic remaining tail; no infinite baseline."""
        last = max((r['end_s'] for r in owners), default=history_start)
        if last <= history_start:
            return dict(full_episode_increment_J_proxy=self.shared*self.tau*initial_shared,
                        remaining_tail_J_proxy=self.shared*self.tau*initial_shared, last_available_s=last)
        cost = self.observe(owners, history_start, last, history_start, initial_shared)
        remaining = self.shared * self.tau * cost['shared_activation_state']
        return dict(full_episode_increment_J_proxy=cost['increment_J_proxy']+remaining,
                    remaining_tail_J_proxy=remaining, last_available_s=last,
                    fixed_baseline_not_integrated_to_infinity=True)

    def marginal(self, past_owners, nominal_reservations, candidate, now, horizon, history_start=0., initial_shared=0.):
        """Exact incremental cost of a public nominal continuation, not a rollout.

        past_owners must end by now. Reservations are explicit estimates of
        existing owners' remaining work. Future actual durations/arrivals must
        never be supplied. This uses the same integral as final evaluation.
        """
        if any(r['end_s'] > now for r in past_owners):
            raise ValueError('Future realized owner in public prefix')
        if any(r['start_s'] < now for r in nominal_reservations):
            raise ValueError('Nominal reservation must start at/after now')
        if candidate['start_s'] != now or candidate['end_s'] > horizon:
            raise ValueError('Candidate must start now and end inside horizon')
        before = [*past_owners, *nominal_reservations]
        base = self.observe(before, now, horizon, history_start, initial_shared)
        added = self.observe([*before, candidate], now, horizon, history_start, initial_shared)
        eb = self.episode(before, history_start, initial_shared)
        ea = self.episode([*before, candidate], history_start, initial_shared)
        terms = ('additive_route_J_proxy', 'identified_pair_credit_J_proxy',
                 'hypothesized_pair_credit_J_proxy', 'hypothesized_idle_tail_J_proxy')
        return dict(status='PUBLIC_NOMINAL_COST_ESTIMATE',
            marginal_window_J_proxy=added['increment_J_proxy']-base['increment_J_proxy'],
            marginal_full_episode_J_proxy=ea['full_episode_increment_J_proxy']-eb['full_episode_increment_J_proxy'],
            decomposition={k: added[k]-base[k] for k in terms},
            initial_shared_activation_state=self.observe(past_owners, history_start, now, history_start, initial_shared)['shared_activation_state'] if now > history_start else initial_shared,
            future_actual_durations_used=False, future_arrivals_used=False,
            prediction_error_and_missing_future_competition_not_eliminated=True,
            measured_J=None)
