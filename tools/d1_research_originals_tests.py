"""Read-only original-source regression runner with explicit path relocation."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import unittest

MODULES = [
    'tools.test_d1_simulation_model_v2', 'tools.test_d1_simulation_model_v2_campaign',
    'tools.test_d1_simulation_model_v2_report', 'tools.test_d1_simulation_model_v3',
    'tools.test_d1_simulation_model_v3_campaign', 'tools.test_d1_simulation_model_v3_energy',
    'tools.test_d1_simulation_model_v3_hybrid_report', 'tools.test_d1_simulation_model_v3_inputs',
    'tools.test_d1_simulation_model_v3_prediction', 'tools.test_d1_simulation_model_v3_report',
    'tools.test_d1_simulation_model_v3_thermal',
]


def relocated_string(value, workspace, external):
    normalized = value.replace('\\', '/')
    for current in (workspace, external):
        prefix = str(current).replace('\\', '/').rstrip('/') + '/'
        if normalized.casefold().startswith(prefix.casefold()):
            return value
    if not (len(normalized) > 2 and normalized[1:3] == ':/'):
        return value
    for marker, root in [('D1Check-model02b/', workspace), ('D1Check_Arrival_Extension/', external)]:
        pos = normalized.find(marker)
        if pos >= 0:
            suffix = normalized[pos + len(marker):]
            destination = (root / suffix).resolve()
            if not destination.is_relative_to(root.resolve()):
                raise ValueError('historical path escapes source root')
            return str(destination)
    return value


def relocated_metadata(value, workspace, external):
    if isinstance(value, str): return relocated_string(value, workspace, external)
    if isinstance(value, list): return [relocated_metadata(v, workspace, external) for v in value]
    if isinstance(value, dict):
        result = {relocated_string(k, workspace, external): relocated_metadata(v, workspace, external) for k, v in value.items()}
        if len(result) != len(value): raise ValueError('historical path-key collision')
        return result
    return value


def run(snapshot, report):
    snapshot = Path(snapshot).resolve(); workspace = snapshot/'workspace'; external = snapshot/'external'
    if not (workspace/'tools/test_d1_simulation_model_v3_inputs.py').exists():
        raise ValueError('restore original source and required raw inputs first')
    # Original file bytes remain untouched. Only loaded path strings/keys change.
    original_loads = json.loads
    def loads(*args, **kwargs):
        return relocated_metadata(original_loads(*args, **kwargs), workspace, external)
    json.loads = loads
    sys.path.insert(0, str(workspace))
    import tools
    tools.__path__ = [str(workspace/'tools')]
    suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    patched = []
    for name, module in list(sys.modules.items()):
        if name.startswith('tools.') and module is not None and hasattr(module, 'EXTERNAL'):
            setattr(module, 'EXTERNAL', external); patched.append(name)
    # One historical test uses a repository-relative raw plan.
    import os
    previous = Path.cwd(); os.chdir(workspace)
    try: result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally: os.chdir(previous); json.loads = original_loads
    value = dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        successful=result.wasSuccessful(), original_sources=True, file_bytes_modified=False,
        relocation='in-memory absolute path strings and keys; numeric/boolean/array values unchanged',
        external_modules_rebound=patched, new_learning=0, device_commands=0)
    Path(report).parent.mkdir(parents=True, exist_ok=True)
    Path(report).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    return result.wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.snapshot, args.report) else 1)


if __name__ == '__main__': main()
