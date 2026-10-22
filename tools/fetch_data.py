"""Restore published data, checking ZIP and member hashes; no experiments."""
import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--match', default='', help='Restore only paths containing this text')
    args = parser.parse_args()
    files = json.loads((ROOT / 'data/FILES.json').read_text(encoding='utf-8'))['files']
    assets = json.loads((ROOT / 'data/ASSETS.json').read_text(encoding='utf-8'))['assets']
    chosen = [r for r in files if r['storage'] == 'release' and args.match in r['path']]
    needed = []
    for row in chosen:
        path = ROOT / row['path']
        if path.is_file():
            if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
                raise RuntimeError('Existing file differs; preserved: ' + row['path'])
        else:
            needed.append(row)
    cache = ROOT / '.data-cache'
    cache.mkdir(exist_ok=True)
    restored = 0
    for asset in assets:
        rows = [r for r in needed if r['asset'] == asset['name']]
        if not rows:
            continue
        archive = cache / asset['name']
        url = asset['url']
        if not url.startswith('https://github.com/mingyujo/D1Check/releases/download/'):
            raise RuntimeError('Unexpected release location')
        if not archive.is_file() or archive.stat().st_size != asset['bytes'] or digest(archive) != asset['sha256']:
            temporary = archive.with_suffix('.download')
            print('Downloading ' + asset['name'], flush=True)
            request = urllib.request.Request(url, headers={'User-Agent': 'D1Check-data-reader'})
            with urllib.request.urlopen(request, timeout=120) as source, temporary.open('wb') as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            if temporary.stat().st_size != asset['bytes'] or digest(temporary) != asset['sha256']:
                raise RuntimeError('Release ZIP hash mismatch: ' + asset['name'])
            temporary.replace(archive)
        with zipfile.ZipFile(archive) as zipped:
            for row in rows:
                relative = PurePosixPath(row['path'])
                if relative.is_absolute() or '..' in relative.parts:
                    raise RuntimeError('Unsafe manifest path')
                target = ROOT.joinpath(*relative.parts)
                if not target.resolve().is_relative_to(ROOT.resolve()):
                    raise RuntimeError('Path leaves checkout')
                info = zipped.getinfo(row['member'])
                if info.file_size != row['bytes']:
                    raise RuntimeError('ZIP member size mismatch: ' + row['path'])
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + '.download')
                with zipped.open(info) as source, temporary.open('wb') as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                if digest(temporary) != row['sha256']:
                    raise RuntimeError('ZIP member hash mismatch: ' + row['path'])
                temporary.replace(target)
                restored += 1
        print('Verified ' + asset['name'], flush=True)
    if len(needed) != restored:
        raise RuntimeError('No release asset found for some selected files')
    print(json.dumps({'status': 'PASS', 'restored_files': restored, 'selected_files': len(chosen), 'new_experiments': 0}))


if __name__ == '__main__':
    main()
