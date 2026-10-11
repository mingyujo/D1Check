import datetime as dt
import importlib.metadata as meta
import json
import os
from pathlib import Path
import platform
import sys

base=Path(__file__).resolve().parent
site=base/'cpuenv/Lib/site-packages'
def stamps(p):
    s=p.stat()
    return dict(created_utc=dt.datetime.fromtimestamp(s.st_ctime,dt.timezone.utc).isoformat(),modified_utc=dt.datetime.fromtimestamp(s.st_mtime,dt.timezone.utc).isoformat(),filesystem_write_interval_seconds=max(0,s.st_mtime-s.st_ctime))

import numpy as np
import torch
q=dict(os=platform.platform(),architecture=platform.machine(),python=sys.version,logical_cpu_count=os.cpu_count(),cpu='AMD Ryzen 5 5600 6-Core Processor',physical_cores=6,ram_bytes=16717836*1024,initial_disk_free_bytes=57061486592,packages={p:meta.version(p) for p in ('numpy','torch','matplotlib')},torch_num_threads=torch.get_num_threads(),torch_cuda_build=torch.version.cuda,device='cpu',venv_isolated=sys.prefix!=sys.base_prefix,venv_system_site_packages=False,original_host_packages_preserved={'numpy':'2.1.3','torch':'2.7.1+cu118','matplotlib':'3.10.9'},official_sources={'numpy_matplotlib':'https://pypi.org/simple','torch':'https://download.pytorch.org/whl/cpu','zip':'https://raw.githubusercontent.com/mingyujo/D1Check/feature/arrival-scheduling-20260923/docs/results/desktop_handoff_20261011/D1Check-desktop-cpu-20261011.zip'},download_zip_file_timestamps=stamps(base/'D1Check-desktop-cpu-20261011.zip'),venv_configuration_file_timestamps=stamps(base/'cpuenv/pyvenv.cfg'),numpy_install_record_timestamps=stamps(site/'numpy-2.4.6.dist-info/RECORD'),torch_install_record_timestamps=stamps(site/'torch-2.11.0+cpu.dist-info/RECORD'),download_install_timing_note='filesystem timestamps give separate recorded bounds, not a complete network/installer stopwatch; functional verification commands have measured wall and CPU stage receipts',cross_host_bitwise_equivalence_claimed=False)
q['installation_filesystem_span_seconds']=max(0,(site/'torch-2.11.0+cpu.dist-info/RECORD').stat().st_mtime-(base/'cpuenv/pyvenv.cfg').stat().st_ctime)
(base/'environment.json').write_text(json.dumps(q,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(q,ensure_ascii=False,indent=2))
