"""Download/verify/restore research originals; never starts a phone or training."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'docs/results/research_originals_20261011'


def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def long_path(path):
    path = str(Path(path).absolute())
    return Path('\\\\?\\' + path) if os.name == 'nt' and not path.startswith('\\\\?\\') else Path(path)


def safe_target(root, relative):
    parts = PurePosixPath(relative).parts
    if not parts or PurePosixPath(relative).is_absolute() or '..' in parts or any(':' in p for p in parts):
        raise ValueError('unsafe archive path')
    root = Path(root).resolve()
    destination = root.joinpath(*parts).resolve()
    if not destination.is_relative_to(root):
        raise ValueError('destination escapes restore root')
    return long_path(destination)


def load_manifest(path=None):
    path = Path(path or PUBLIC / 'files.json.gz')
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        manifest = json.load(stream)
    if manifest['schema'] != 1:
        raise ValueError('unsupported originals manifest')
    return manifest


def download(manifest, cache):
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True)
    receipt = []
    for asset in manifest['assets']:
        path = cache / asset['name']
        if path.exists():
            if path.stat().st_size != asset['bytes'] or digest_file(path) != asset['sha256']:
                raise ValueError('existing download differs: ' + asset['name'])
            receipt.append(dict(name=asset['name'], reused=True))
            continue
        temporary = cache / (asset['name'] + '.partial')
        if temporary.exists():
            raise ValueError('incomplete earlier download; inspect before retry: ' + str(temporary))
        request = urllib.request.Request(asset['url'], headers={'User-Agent': 'D1Check-originals-restore'})
        h = hashlib.sha256(); size = 0
        with urllib.request.urlopen(request, timeout=60) as source, temporary.open('xb') as target:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk: break
                target.write(chunk); h.update(chunk); size += len(chunk)
        if size != asset['bytes'] or h.hexdigest() != asset['sha256']:
            raise ValueError('download SHA mismatch: ' + asset['name'])
        temporary.rename(path)
        print('downloaded', asset['name'], size, flush=True)
        receipt.append(dict(name=asset['name'], bytes=size, sha256=h.hexdigest()))
    return receipt


def verify_assets(manifest, cache):
    cache = Path(cache)
    rows = []
    for asset in manifest['assets']:
        path = cache / asset['name']
        if path.stat().st_size != asset['bytes'] or digest_file(path) != asset['sha256']:
            raise ValueError('archive SHA mismatch: ' + asset['name'])
        rows.append(dict(name=asset['name'], sha256=asset['sha256'], bytes=asset['bytes']))
    return rows


def restore(manifest, cache, destination, namespaces=None, prefixes=None):
    verify_assets(manifest, cache)
    destination = Path(destination).resolve(); destination.mkdir(parents=True, exist_ok=True)
    opened = {}; restored = reused = total = 0
    try:
        for row in manifest['files']:
            if namespaces and row['namespace'] not in namespaces: continue
            key = row['namespace'] + '/' + row['path']
            if prefixes and not any(key.startswith(p) for p in prefixes): continue
            target = safe_target(destination, key)
            if target.exists():
                if target.stat().st_size != row['bytes'] or digest_file(target) != row['sha256']:
                    raise ValueError('existing original differs; overwrite prohibited: ' + key)
                reused += 1; continue
            if row['asset'] not in opened:
                opened[row['asset']] = zipfile.ZipFile(Path(cache) / row['asset'])
            archive = opened[row['asset']]
            info = archive.getinfo(row['member'])
            if info.file_size != row['bytes'] or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('invalid member metadata: ' + key)
            target.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256(); size = 0
            with archive.open(info) as source, target.open('xb') as sink:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk: break
                    sink.write(chunk); h.update(chunk); size += len(chunk)
            if size != row['bytes'] or h.hexdigest() != row['sha256']:
                raise ValueError('restored source SHA mismatch: ' + key)
            restored += 1; total += size
            if restored % 5000 == 0: print('restored', restored, flush=True)
    finally:
        for archive in opened.values(): archive.close()
    receipt = dict(restored_files=restored, reused_files=reused, restored_bytes=total,
                   original_bytes_verified=True, new_device_commands=0, new_learning=0)
    (destination / 'RESTORE_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['download', 'verify', 'restore'])
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--cache', type=Path, default=ROOT/'output/research_originals_download_20261011')
    parser.add_argument('--destination', type=Path, default=ROOT/'output/research_originals_restored_20261011')
    parser.add_argument('--namespace', action='append')
    parser.add_argument('--prefix', action='append', help='namespace/repository-relative path prefix; repeatable')
    args = parser.parse_args(); manifest = load_manifest(args.manifest)
    if args.action == 'download': result = download(manifest, args.cache)
    elif args.action == 'verify': result = verify_assets(manifest, args.cache)
    else: result = restore(manifest, args.cache, args.destination, args.namespace, args.prefix)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
