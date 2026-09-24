"""Read-only APK update preflight. No install, launch, keystore access or device writes."""
from pathlib import Path
import json
import re
import subprocess
import time

from tools import d1_arrival_plan as p


def inspect(apk, toolchain, deadline=None):
    apk = Path(apk)
    def limit(seconds):
        remaining = seconds if deadline is None else min(seconds, deadline-time.monotonic())
        if remaining <= 0:
            raise TimeoutError('APK inspection deadline exhausted')
        return remaining
    cert = subprocess.run([toolchain['java'], '-jar', toolchain['apksigner'],
                           'verify', '--verbose', '--print-certs', str(apk)],
                          capture_output=True, text=True, check=True, timeout=limit(60)).stdout
    badging = subprocess.run([toolchain['aapt2'], 'dump', 'badging', str(apk)],
                            capture_output=True, text=True, check=True, timeout=limit(30)).stdout
    package = re.search(r"^package: name='([^']+)' versionCode='(\d+)'", badging, re.M)
    signers = re.findall(r'Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})', cert)
    count = re.search(r'Number of signers: (\d+)', cert)
    if not package or not count or int(count[1]) != 1 or len(signers) != 1:
        raise ValueError('APK identity unavailable or unsupported multiple signers')
    return dict(package=package[1], version_code=int(package[2]),
                signer_sha256=signers[0].lower(), apk_sha256=p.digest(apk))


def compatible(candidate, installed, expected):
    if candidate != expected:
        raise ValueError('candidate differs from frozen APK identity')
    if candidate['package'] != installed['package']:
        raise ValueError('applicationId mismatch')
    if candidate['signer_sha256'] != installed['signer_sha256']:
        raise ValueError('signer mismatch (rotation/lineage not assumed compatible)')
    if candidate['version_code'] < installed['version_code']:
        raise ValueError('versionCode downgrade')


def preflight(device, plan, output):
    """An unsuccessful check consumes neither phase nor session. Evidence is write-once."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    result = dict(status='PREFLIGHT_FAILED', install_attempts=0, session_attempts=0,
                  phase_consumed=False, plan_sha256=p.digest(plan['_plan_file']))
    try:
        result['device'] = device.identify(plan['device_fingerprint'])
        tools = plan['apk_preflight']['toolchain']
        for name, digest in plan['apk_preflight']['tool_sha256'].items():
            if p.digest(tools[name]) != digest:
                raise ValueError('APK inspection tool identity changed: ' + name)
        candidate = inspect(plan['apk_path'], tools, deadline=device.deadline)
        result['candidate'] = candidate
        response = device.call('shell', 'pm', 'path', candidate['package'])
        paths = response.stdout.decode().splitlines()
        # The approved app is a single base APK; absence/splits are not silently accepted.
        if len(paths) != 1 or not re.fullmatch(r'package:/data/app/[A-Za-z0-9_+./=~-]+/base\.apk', paths[0].strip()):
            raise ValueError('installed base APK unavailable or unsupported split layout')
        remote = paths[0].strip()[len('package:'):]
        device.call('pull', remote, str(output / 'installed-base.apk'), timeout=180)
        installed = inspect(output / 'installed-base.apk', tools, deadline=device.deadline)
        result['installed'] = installed
        compatible(candidate, installed, plan['apk_preflight']['candidate'])
        result['status'] = 'PREFLIGHT_COMPATIBLE_NOT_INSTALLED'
        return result
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        with (output / 'preflight.json').open('xb') as stream:
            stream.write(p.canonical(result))


def main():
    import argparse
    from tools import d1_arrival_device as d
    from tools import d1_arrival_timing_calibration as c
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('plan', 'adb', 'serial', 'output'):
        parser.add_argument('--' + arg, required=True)
    args = parser.parse_args()
    c.check(args.plan, for_execution=True)
    plan = p.read(args.plan)
    if 'apk_preflight' not in plan:
        raise ValueError('plan has no frozen signature gate; do not reuse a stopped plan')
    plan['_plan_file'] = args.plan
    print(json.dumps(preflight(d.Device(args.adb, args.serial), plan, args.output), indent=2))


if __name__ == '__main__':
    main()
