"""Portable integrated cost observer for any A24 predicted CPU/GPU schedule.

No simulation, training, network or device command is triggered by this API.
The same model evaluates novel schedules; this is not a saved-outcome lookup.
The preceding policy checkpoint's own features/reward are intentionally unchanged.
"""
from pathlib import Path
import hashlib,json
import state_cost as C
import relative_drain as R

ROOT=Path(__file__).resolve().parents[2]

class CostObserver:
    def __init__(self,root=ROOT):
        self.root=Path(root)
        self.bundle=json.loads((self.root/'experiments/competition_cost_20261017/COST_BUNDLE.json').read_text(encoding='utf-8'))
        for spec in self.bundle['pins']:
            if hashlib.sha256((self.root/spec['path']).read_bytes()).hexdigest()!=spec['sha256']:
                raise ValueError('Cost bundle source/model SHA differs: '+spec['path'])
        self.model=json.loads((self.root/self.bundle['state_model']).read_text(encoding='utf-8'))
        self.native=json.loads((self.root/self.bundle['relative_model']).read_text(encoding='utf-8'))['model']

    def observe(self,summary,lo,hi,baseline_W_proxy=C.BASELINE):
        """lo/hi must be fixed from the common input before choosing a policy.

        summary.gantt owns CPU/GPU from dispatch through actual predicted
        AVAILABLE. Never replace that boundary with output-ready or inference-end.
        """
        if not 0<=lo<hi<=210:raise ValueError('Common A24 forecast window')
        owners=summary['gantt']
        intervals=R.exclusive(owners,0.,210.)
        return dict(schema='A24-integrated-cost-observation-v2',
                    window_s=[lo,hi],conditional_state_cost=C.observe(intervals,lo,hi,self.model,baseline_W_proxy),
                    native_current_index=R.observe(owners,lo,hi,self.native),
                    predictive_for_new_schedules=True,simulations_started=0,NN_updates=0,
                    measured_J=None,energy_error_J=None,energy_CI=None,
                    policy_feature_distribution_changed=False,
                    warning='Unmeasured routes use explicit transfer sensitivity; native index may be unqualified. J* is not calibrated J.')

    def annotate(self,summary,lo,hi,baseline_W_proxy=C.BASELINE):
        """Return a new summary; preserve all preceding observations/metrics."""
        return {**summary,'cost_model_v2':self.observe(summary,lo,hi,baseline_W_proxy)}
