"""Create a hash-guarded Ente observation overlay, never build/run an app."""
import argparse
import hashlib
import json
from pathlib import Path
from tools.d1_real_app_baseline_check import SOURCES, COMMIT

IMPORT = 'import "package:photos/services/machine_learning/d1_baseline_trace.dart";\n'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('source anchor is missing or ambiguous')
    return text.replace(old, new, 1)


def instrument(source):
    """Only insert observations and passthrough returns; no policy constants change."""
    service = source['ml_service.dart']
    start = service.index('  Future<MlRunDisposition> runAllML({')
    end = service.index('  // FG-only: one coalesced retry', start)
    region = service[start:end]
    region = replace_once(region, 'final runControl = control ?? MlRunControl();',
                          'final runControl = control ?? MlRunControl();\n'
                          '    D1BaselineTrace.emit(runControl, "run_enter");')
    for disposition in ['stopped', 'denied']:
        region = region.replace(f'return MlRunDisposition.{disposition};',
            f'return D1BaselineTrace.finish(runControl, MlRunDisposition.{disposition});')
    region = replace_once(region, '    var disposition = MlRunDisposition.completed;',
        '    D1BaselineTrace.emit(runControl, "admission_passed");\n'
        '    var disposition = MlRunDisposition.completed;')
    region = replace_once(region, '      computeController.releaseCompute(ml: true);',
        '      D1BaselineTrace.emit(runControl, "release_requested");\n'
        '      computeController.releaseCompute(ml: true);\n'
        '      D1BaselineTrace.emit(runControl, "release_returned");')
    region = replace_once(region, '    return disposition;',
        '    return D1BaselineTrace.finish(runControl, disposition);')
    service = service[:start] + region + service[end:]
    service = replace_once(service,
        '      if (canFetch()) {\n        await _fetchAndIndexAllImages(',
        '      if (canFetch()) {\n'
        '        D1BaselineTrace.emit(control, "indexing_enter");\n'
        '        await _fetchAndIndexAllImages(')
    service = replace_once(service,
        '          allowImageIndexing: allowImageIndexing,\n        );',
        '          allowImageIndexing: allowImageIndexing,\n        );\n'
        '        D1BaselineTrace.emit(control, "indexing_returned");')
    control = replace_once(source['ml_run_control.dart'],
        '    _stopReason = reason;',
        '    _stopReason = reason;\n'
        '    D1BaselineTrace.emit(this, "stop_latched", reason.name);')
    service = replace_once(service,
        'import "package:photos/services/machine_learning/face_ml/face_clustering/face_clustering_service.dart";\n',
        IMPORT + 'import "package:photos/services/machine_learning/face_ml/face_clustering/face_clustering_service.dart";\n')
    control = replace_once(control, 'import "package:logging/logging.dart";\n',
        'import "package:logging/logging.dart";\n' + IMPORT)
    return {'ml_service.dart': service, 'ml_run_control.dart': control}


def prepare(source_dir, output_dir):
    originals = {}
    for name, expected in SOURCES.items():
        raw = (source_dir / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('upstream hash mismatch: ' + name)
        originals[name] = raw.decode('utf-8').replace('\r\n', '\n')
    transformed = instrument(originals)
    transformed['d1_baseline_trace.dart'] = Path(__file__).with_name(
        'ente_baseline_trace.dart').read_text(encoding='utf-8')
    # Refuse to reuse an output directory or alter the source checkout.
    output_dir.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name, text in transformed.items():
        raw = text.encode('utf-8'); (output_dir / name).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    receipt = dict(upstream_commit=COMMIT, source_sha256=SOURCES,
                   overlay_sha256=hashes, enabled_by_default=False,
                   dart_compiled=False, app_executed=False,
                   device_commands=0, experiment_ready=False)
    (output_dir / 'overlay_receipt.json').write_text(
        json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source_dir, args.output_dir), indent=2))


if __name__ == '__main__':
    main()
