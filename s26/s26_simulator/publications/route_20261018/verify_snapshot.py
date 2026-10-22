"""Read-only SHA verification of the published S26 snapshot; no simulation."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Path outside repository: ' + relative)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', required=True, type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    manifest = json.loads(Path(__file__).with_name('SNAPSHOT_FILES.json').read_text(encoding='utf-8'))
    failed = []
    for item in manifest['files']:
        path = safe_path(root, item['path'])
        if not path.is_file():
            failed.append({'path': item['path'], 'reason': 'missing'})
        elif path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            failed.append({'path': item['path'], 'reason': 'different bytes'})
    print(json.dumps({'status': 'FAIL' if failed else 'PASS', 'files': len(manifest['files']),
                      'failures': failed, 'new_simulator_instances': 0, 'new_training': 0}, indent=2))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
