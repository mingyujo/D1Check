"""One fresh HAL observation after baseline; no retry or temperature waiting."""
import math
import re
import time
from pathlib import Path
from tools import d1_energy_collection_device as device
from tools import d1_arrival_device as legacy
from tools import d1_arrival_plan as p

VERSION = 'numeric-ap-once-v1'
DIAGNOSTIC_VERSION = 'numeric-ap-observe-v2'

def approve(d, remote, folder, manifest):
    folder=Path(folder)
    ready=p.read(device.pull_file(d,remote,'start_ap.ready.json',folder/'start_ap_gate'))
    digest=p.digest(folder/'input_manifest.json')
    if ready['manifest_sha256'] != digest:
        raise ValueError('start AP manifest mismatch')
    sample=device.thermal(d,folder,-1)
    ap=float(sample.get('AP') or 'nan')
    mode=manifest.get('start_ap_gate',VERSION)
    if mode not in (VERSION,DIAGNOSTIC_VERSION):
        raise ValueError('unknown start AP mode')
    if not (math.isfinite(ap) and (mode==DIAGNOSTIC_VERSION or 32.5 <= ap <= 34.0) and sample['thermal_status']=='0' and
            ready['mono_ns'] <= sample['before_ns'] <= sample['after_ns'] and
            sample['after_ns']-sample['before_ns'] <= 3_000_000_000):
        raise ValueError('start AP invalid; no arm, no retry')
    sid=manifest['session_id']
    if not re.fullmatch(r'[a-f0-9-]{36}',sid):
        raise ValueError('unsafe session ID')
    # Numeric/hash-only payload; atomic publish prevents app reading partial bytes.
    payload=f"{digest} {int(ready['mono_ns'])} {int(sample['before_ns'])} {int(sample['after_ns'])} {ap:.17g} 0"
    target=f'files/arrival-scheduler-inputs/{sid}/start_ap.arm'
    submitted=time.monotonic()
    d.call('shell','run-as',legacy.PACKAGE,'sh','-c',
           f'"echo {payload} > {target}.tmp && mv {target}.tmp {target}"',timeout=5)
    returned=time.monotonic()
    device.save(folder/'start_ap_gate/host_approval.json',dict(sample=sample,manifest_sha256=digest,
                mode=mode,initial_ap_in_frozen_development_range=(32.5<=ap<=34.0),
                approval_submit_host_monotonic=submitted,approval_return_host_monotonic=returned,
                meaning='approval sent; app must still validate age at actual common start'))
