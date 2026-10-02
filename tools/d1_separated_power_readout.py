"""Explicit portable replay for separated-power v1; no device calls or fitting."""
import argparse
import json
from pathlib import Path
from tools import d1_online_policy_readout as shared
from tools import d1_separated_power_protocol as protocol


def predict(bundle, case_id, policy, output):
    bundle, output = Path(bundle), Path(output)
    resources = shared.p.read(bundle / 'resources.json')
    bindings = resources['files']
    if not {'model.json', 'initial_inputs.json'} <= bindings.keys():
        raise ValueError('required bundle bindings')
    for name, digest in bindings.items():
        path = (bundle / name).resolve()
        if path.parent != bundle.resolve() or shared.p.digest(path) != digest:
            raise ValueError('bundle identity')
    frozen = shared.p.read(bundle / 'model.json')
    if (frozen.get('version') != 'separated-power-model-v1'
            or frozen.get('preload_power_window_s') != [-20, 30]
            or frozen.get('energy_baseline_mode') != 'session_preload'):
        raise ValueError('registered model and initial window required')
    cases = [c for c in shared.p.read(bundle / 'initial_inputs.json') if c['id'] == case_id]
    if len(cases) != 1 or policy not in shared.model.POLICIES:
        raise ValueError('registered initial input/policy required')
    case = cases[0]
    protocol.validate(case['phase'], case['manifest_requests'])
    initial = {key: case['initial'][key] for key in ('preload', 'preload_power_w')}
    ledger, segments = shared.model.forecast(initial, case['manifest_requests'], policy,
                                            frozen, planning_input_role=case['phase'])
    costs = shared.model.costs(segments, initial, list(range(35, 181)), frozen, 180)
    output.mkdir(parents=True, exist_ok=False)
    shared.write(output / 'result.json', dict(
        route='separated-power-v1', policy=policy, initial_case_id=case_id,
        forecast=ledger, costs=costs, uses_future_measurements=False,
        initialization='registered pre35 AP and pre[-20,30] mean whole-device W',
        model_sha256=bindings['model.json'], initial_inputs_sha256=bindings['initial_inputs.json'],
        scope=frozen['scope'], accuracy_pass=None, experiment_ready=False, device_commands=0))
    return dict(output=str(output), whole_120s_j=costs['whole_120s_j'], device_commands=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('bundle', 'case-id', 'policy', 'output'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    print(json.dumps(predict(args.bundle, args.case_id, args.policy, args.output), indent=2))


if __name__ == '__main__':
    main()
