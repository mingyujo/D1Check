"""Download, verify and restore S26 archived bytes. Never executes scientific code."""
import argparse
import json
import os
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from verify_snapshot import digest, safe_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', required=True, type=Path)
    parser.add_argument('--assets-dir', type=Path)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    root = args.repo_root.resolve()
    here = Path(__file__).resolve().parent
    assets = json.loads((here / 'ASSETS.json').read_text(encoding='utf-8'))
    snapshot_file = here / 'SNAPSHOT_FILES.json'
    if digest(snapshot_file) != assets['snapshot_manifest_sha256']:
        raise RuntimeError('Snapshot manifest SHA mismatch')
    snapshot = json.loads(snapshot_file.read_text(encoding='utf-8'))
    expected = {item['path']: item for item in snapshot['files']}
    asset_dir = (args.assets_dir or root / '.s26-release-cache' / assets['tag']).resolve()
    asset_dir.mkdir(parents=True, exist_ok=True)
    for asset in assets['archives']:
        archive = safe_path(asset_dir, asset['name'])
        if not archive.exists():
            if not args.download:
                raise RuntimeError('Missing archive; supply --download or --assets-dir: ' + asset['name'])
            temporary = archive.with_suffix(archive.suffix + '.partial')
            print('Downloading ' + asset['name'], flush=True)
            request = urllib.request.Request(asset['download_url'], headers={'User-Agent': 'S26-snapshot-restore'})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as out:
                for block in iter(lambda: response.read(1024 * 1024), b''):
                    out.write(block)
            if temporary.stat().st_size != asset['bytes'] or digest(temporary) != asset['sha256']:
                raise RuntimeError('Downloaded archive SHA/size mismatch: ' + asset['name'])
            os.replace(temporary, archive)
        if archive.stat().st_size != asset['bytes'] or digest(archive) != asset['sha256']:
            raise RuntimeError('Archive SHA/size mismatch: ' + asset['name'])
        restored = 0
        with zipfile.ZipFile(archive) as zipped:
            members = zipped.infolist()
            expected_names = {p for p, item in expected.items() if item['archive'] == asset['name']}
            if len(members) != len(expected_names) or {m.filename for m in members} != expected_names:
                raise RuntimeError('Unexpected or duplicate ZIP entries: ' + asset['name'])
            for member in members:
                item = expected[member.filename]
                destination = safe_path(root, member.filename)
                if member.file_size != item['bytes']:
                    raise RuntimeError('ZIP member size mismatch: ' + member.filename)
                if destination.exists():
                    if not destination.is_file() or destination.stat().st_size != item['bytes'] or digest(destination) != item['sha256']:
                        raise RuntimeError('Refusing to overwrite different existing file: ' + str(destination))
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as out:
                        temporary = Path(out.name)
                        with zipped.open(member) as source:
                            for block in iter(lambda: source.read(1024 * 1024), b''):
                                out.write(block)
                    if digest(temporary) != item['sha256']:
                        raise RuntimeError('ZIP member SHA mismatch: ' + member.filename)
                    if destination.exists():
                        raise RuntimeError('Destination appeared during restore: ' + str(destination))
                    os.replace(temporary, destination)
                    temporary = None
                    restored += 1
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
        print(asset['name'] + ': verified, restored ' + str(restored), flush=True)
    print(json.dumps({'status': 'PASS', 'files': len(expected), 'new_simulator_instances': 0, 'new_training': 0}))


if __name__ == '__main__':
    main()
