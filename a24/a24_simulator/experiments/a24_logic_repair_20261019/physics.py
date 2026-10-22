"""Correct the ORIGINAL idle-tail peak without changing its trajectory/cost."""
import math


def idle_peak(T, z, dt, config, shared):
    """Maximum of the same closed-form RC/tail solution on [0, dt]."""
    tt, tz = config.thermal_tau_s, config.idle_tail_s
    a = T - config.idle_c
    if dt <= 0 or tz <= 0 or shared * z == 0:
        return T
    forcing = config.thermal_resistance * shared * z
    if abs(tz - tt) < 1e-9:
        # Equal-tau limit: (a + b*t) exp(-t/tt).
        b = forcing / tt
        critical = tt - a / b if b else -1.
        temperature = lambda t: config.idle_c + (a + b * t) * math.exp(-t / tt)
    else:
        B = forcing * tz / (tz - tt)
        A = a - B
        # dT/dt=0 => exp(t*(1/tz-1/tt)) = -B*tt/(A*tz).
        if A * B < 0:
            log_ratio = math.log(abs(B)) + math.log(tt) - math.log(abs(A)) - math.log(tz)
            critical = log_ratio / (1 / tz - 1 / tt)
        else:
            critical = -1.
        temperature = lambda t: config.idle_c + A * math.exp(-t / tt) + B * math.exp(-t / tz)
    return max(T, temperature(dt), temperature(critical) if 0 < critical < dt else T)


def make_physics_class(base):
    class Physics(base):
        def __init__(self, model, config, profile, shape):
            if profile != 'ORIGINAL':
                raise ValueError('Logic repair v1 is scoped to the ORIGINAL profile')
            super().__init__(model, config, profile, shape)

        def transition(self, state, active, dt):
            after, terms = super().transition(state, active, dt)
            if not active:
                terms['peak'] = max(terms['peak'], idle_peak(
                    state['temperature_c'], state['shared_z'], dt, self.c, self.shared))
            return after, terms
    return Physics
