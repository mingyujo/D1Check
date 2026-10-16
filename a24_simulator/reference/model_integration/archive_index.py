"""Recover member byte hashes for received old archives missing that index.

This stage parses no JSON/CSV/session outcomes. Old CRC receipts stay unchanged.
"""
import hashlib
from pathlib import PurePosixPath
import re
import zipfile

from runtime_guard import pin


def safe_info(info):
    original = info.orig_filename
    if original != info.filename or '\\' in original or '\x00' in original:
        raise ValueError('Normalized or unsafe ZIP name')
    path = PurePosixPath(original.rstrip('/'))
    if path.is_absolute() or any(x in ('', '.', '..') for x in path.parts) or re.match(r'^[a-zA-Z]:', original):
        raise ValueError('Absolute/traversal ZIP name')
    if (info.external_attr >> 16) & 0o170000 == 0o120000:
        raise ValueError('Symlink ZIP member')
    return original


def index_archives(specs, expanded_cap=1024**3, member_cap=100000):
    reports, expanded, count = [], 0, 0
    for spec in specs:
        path = pin(spec)
        hashes, sizes = {}, {}
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [safe_info(x) for x in infos]
            if len(names) != len(set(names)):
                raise ValueError('Duplicate archive names')
            for info in infos:
                if info.is_dir():
                    continue
                expanded += info.file_size
                count += 1
                if expanded > expanded_cap or count > member_cap:
                    raise ValueError('Registered opaque indexing limit exceeded')
                h, size = hashlib.sha256(), 0
                with archive.open(info) as stream:
                    for block in iter(lambda: stream.read(1024**2), b''):
                        h.update(block)
                        size += len(block)
                if size != info.file_size:
                    raise ValueError('Expanded ZIP size mismatch')
                hashes[info.filename] = h.hexdigest()
                sizes[info.filename] = size
        reports.append({'path':str(path),'sha256':spec['sha256'],'bytes':path.stat().st_size,
                        'CRC':'PASS','CRC_method':'Each selected received archive member streamed to EOF',
                        'member_hashes':hashes,'member_bytes':sizes,'members':len(hashes),
                        'new_semantic_payloads_parsed':0,'outcome_request_sensor_KPI_semantics_parsed':False})
    return reports
