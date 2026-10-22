"""Same frozen 50-feature BC, with a declared pre-selection idle WAIT guard."""
import copy
from a24_atc_bc_20261019 import load_components as load_base

BasePolicy = load_base().Policy
from common_transfer import ACTIONS, np
from a24_atc_bc_20261019.candidates import compatible_targets
from . import VERSION, NETWORK_VERSION
from .guard import filter_idle_waits


class Policy(BasePolicy):
    @staticmethod
    def guard_bank(s, bank, actions):
        bank = dict(bank)
        bank['physical_mask'] = bank['mask'].copy()
        bank['mask'], bank['idle_wait_guard'] = filter_idle_waits(
            s, actions, bank['forecasts'], bank['physical_mask'])
        bank['policy_version'] = VERSION
        assert bank['version'] == NETWORK_VERSION
        return bank

    def encode(self, s):
        bank, actions = super().encode(s)
        return self.guard_bank(s, bank, actions), actions

    def __call__(self, s):
        if self.mode.startswith(('FIFO', 'EDF')):
            return super().__call__(s)
        bank, actions = self.encode(s)
        if self.learner:
            i, frame = self.learner.choose(bank, self.collect)
            frame['time_ns'] = s['now_ns']
            frame['policy_version'] = VERSION
            self.frames.append(frame)
        else:
            allowed = [i for i in range(len(actions)) if bank['mask'][i]]
            i = min(allowed, key=lambda k:(bank['scores'][k], k))
            teacher = np.zeros(ACTIONS, bool)
            teacher[:len(actions)] = compatible_targets(s, actions, i)
            teacher &= bank['mask']
            a = actions[i]
            group = (a['kind'] if a['kind'] != 'DISPATCH' else next(
                q for q in s['queue'] if q['request_id'] == a['request_id'])['task'] + '_' + a['route'])
            self.frames.append(dict(**{k:bank[k] for k in ('x', 'mask', 'scores')},
                index=i, time_ns=s['now_ns'], teacher_mask=teacher, group=group, policy_version=VERSION))
        assert bank['mask'][i]
        a = copy.deepcopy(actions[i])
        self.calls.append(dict(time_ns=s['now_ns'], action=a, chosen=i, actions=actions,
            x=bank['x'].tolist(), mask=bank['mask'].tolist(),
            physical_mask=bank['physical_mask'].tolist(), idle_wait_guard=bank['idle_wait_guard'],
            forecast_scores=bank['scores'].tolist(), forecasts=bank['forecasts'],
            future_information=False, post_NN_override=False, fixed_ATC_prior=False,
            version=VERSION, network_version=NETWORK_VERSION, pre_NN_forecast_filter=True))
        return a
