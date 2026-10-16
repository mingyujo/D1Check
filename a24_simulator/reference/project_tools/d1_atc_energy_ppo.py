"""Fresh reward comparison; frozen DROP_FLAG_WAIT1 ABI and native PPO mechanics."""
import copy
from dataclasses import asdict

import numpy as np
import torch

from tools import d1_atc_waitlink_ppo as native

VERSION = "atc-energy-guard-learner-v13"
COUPLING = "DROP_FLAG_WAIT1"
ARMS = ("CONTROL", "ECO5", "GATED_ECO5", "GATED_ECO5_AP180")
COST_ARMS = ARMS[1:]
OBJECTIVES = {
    "CONTROL": "ENERGY13_URGENT_HOLD_E1_AP1_P95_20",
    "ECO5": "ENERGY13_URGENT_HOLD_E5_AP5_P95_20",
    "GATED_ECO5": "ENERGY13_URGENT_HOLD_E5_AP5_EPISODE_SERVICE_GATE_P95_20",
    "GATED_ECO5_AP180": "ENERGY13_URGENT_HOLD_E5_AP5_FULL_AP180_EPISODE_SERVICE_GATE_P95_20",
}
MULTIPLIERS = {arm: [1. if arm == "CONTROL" else 5.] * 2 + [100.] * 6 + [20.] for arm in ARMS}


class Learner(native.Learner):
    """Ctor/restore differ; inherited _update, loss, Adam settings stay native."""
    def __init__(self, seed, dependencies):
        reward = dependencies.get("reward_arm")
        if (reward not in ARMS or dependencies.get("arm") != COUPLING or
            dependencies.get("sequencing") != "ATC" or
            dependencies.get("schema") != native.policy.SCHEMA or
            dependencies.get("objective") != OBJECTIVES[reward] or
            dependencies.get("multipliers") != MULTIPLIERS[reward] or
            dependencies.get("seed") != seed):
            raise ValueError("fresh reward/source/seed contract")
        super().__init__(seed, dependencies)
        self.reward_arm = reward
        self.objective = OBJECTIVES[reward]
        self.multipliers = np.array(MULTIPLIERS[reward], dtype=np.float64)

    def snapshot(self):
        value = super().snapshot()
        value.update(version=VERSION, reward_arm=self.reward_arm)
        return value

    @classmethod
    def from_snapshot(cls, data, dependencies):
        reward = dependencies.get("reward_arm")
        if (data.get("version") != VERSION or reward not in ARMS or
            data.get("reward_arm") != reward or data.get("seed") != dependencies.get("seed") or
            data.get("schema") != native.policy.SCHEMA or
            data.get("objective") != OBJECTIVES[reward] or
            data.get("dependencies") != dependencies or
            data.get("settings") != asdict(native.native.Settings()) or
            not np.array_equal(data.get("multipliers"), MULTIPLIERS[reward])):
            raise ValueError("energy checkpoint version/objective/multipliers/source/seed mismatch")
        learner = cls(data["seed"], dependencies)
        learner.network.load_state_dict(data["network"])
        learner.optimizer.load_state_dict(data["optimizer"])
        learner.action_rng.set_state(data["action_rng"])
        learner.shuffle_rng.set_state(data["shuffle_rng"])
        for key in ("multipliers", "pending", "logs", "episode_logs", "episodes", "steps",
                    "cursor", "consumption", "last_controller"):
            setattr(learner, key, copy.deepcopy(data[key]))
        native.validate_frames([item["frames"] for item in learner.pending])
        return learner


def targets(controller, raw, baseline_j, reward_arm, reference):
    from tools import d1_atc_energy_targets as labels
    return labels.targets(controller, raw, baseline_j, reward_arm, reference)
