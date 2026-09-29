"""One fresh HAL observation after baseline; no retry or temperature waiting."""
import math
import re
from pathlib import Path
from tools import d1_energy_collection_device as device
from tools import d1_arrival_device as legacy
from tools import d1_arrival_plan as p

VERSION = 'numeric-ap-once-v1'

def approve(d, remote, folder, manifest):
    folder=Path(folder)
    ready=p.read(device.pull_file(d,remote,'start_ap.ready.json',folder/'start_ap_gate'))
    digest=p.digest(folder/'input_manifest.json')
    if ready['manifest_sha256'] != digest:
        raise ValueError('start AP manifest mismatch')
    sample=device.thermal(d,folder,-1)
    ap=float(sample.get('AP') or 'nan')
    if not (math.isfinite(ap) and 32.5 <= ap <= 34.0 and sample['thermal_status']=='0' and
            ready['mono_ns'] <= sample['before_ns'] <= sample['after_ns'] and
            sample['after_ns']-sample['before_ns'] <= 3_000_000_000):
        raise ValueError('start AP invalid; no arm, no retry')
    sid=manifest['session_id']
    if not re.fullmatch(r'[a-f0-9-]{36}',sid):
        raise ValueError('unsafe session ID')
    # Numeric/hash-only payload; atomic publish prevents app reading partial bytes.
    payload=f"{digest} {int(ready['mono_ns'])} {int(sample['before_ns'])} {int(sample['after_ns'])} {ap:.17g} 0"
    target=f'files/arrival-scheduler-inputs/{sid}/start_ap.arm'
    d.call('shell','run-as',legacy.PACKAGE,'sh','-c',
           f'"echo {payload} > {target}.tmp && mv {target}.tmp {target}"',timeout=5)
    device.save(folder/'start_ap_gate/host_approval.json',dict(sample=sample,manifest_sha256=digest,
                meaning='approval sent; app must still validate age at actual common start'))
