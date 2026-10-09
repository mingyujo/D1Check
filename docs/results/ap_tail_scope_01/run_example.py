"""Recorded LOAD_A conditional AP example. Never launches a phone or simulation."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools import d1_ap_tail_scope as api


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--opt-in', action='store_true')
    args = p.parse_args()
    case = next(c for c in api.tail.s.j.m.read(
        ROOT / 'docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz')
        if c['policy'] == 'LOAD_A_LONG')
    context = api.tail.s.j.m.read(Path(__file__).with_name('run_v4') / 'recorded_contexts.json')[case['id']]
    result = api.forecast(case, context, opt_in=args.opt_in)
    ap = result['prediction_ap_c']
    metric = sum(abs(a-b) for a, b in zip(ap, case['ap'])) / len(ap) if ap is not None else None
    result.update(recorded_example=True, observed_AP_used_only_after_prediction=True,
                  recorded_example_mae_c=metric, fit_calls=0, device_commands=0,
                  environment_simulations=0)
    with Path(args.output).open('x', encoding='utf8') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(status=result['status'], AP_MAE_c=metric, device_commands=0,
                          fit_calls=0, strict_support=False, accuracy_pass=None)))


if __name__ == '__main__':
    main()
