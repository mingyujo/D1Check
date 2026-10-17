"""Record the completed operation's local runtime; never starts an environment."""
from pathlib import Path
import hashlib
import json
import os
import platform
import subprocess
import sys
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'reference/model_integration'))
import runtime_guard as G


def main():
    op = json.loads((HERE / 'OPERATION.json').read_text(encoding='utf-8'))
    out = ROOT / op['output_dir']
    G.require((out / 'COMPLETE.json').exists(), 'Completed operation required')
    G.require(not (out / 'ENVIRONMENT.json').exists(), 'Preserve existing runtime record')
    G.OWN_TOKENS += ('coupled_345_20261017',)
    guard = G.process_guard(Path(__file__).resolve())
    G.free_guard([ROOT, 'D:/'])
    torch.set_num_threads(1)
    command = ['git', 'rev-parse', 'HEAD']
    revision = subprocess.check_output(command, cwd=ROOT.parent, text=True).strip()
    value = dict(
        schema='A24-coupled345-local-runtime-v1',
        python=sys.version, executable=sys.executable,
        numpy=np.__version__, torch=torch.__version__,
        platform=platform.platform(), machine=platform.machine(),
        torch_threads=torch.get_num_threads(),
        OMP_NUM_THREADS=os.environ.get('OMP_NUM_THREADS'),
        MKL_NUM_THREADS=os.environ.get('MKL_NUM_THREADS'),
        torch_build=torch.__config__.show(), capture_commit=revision,
        original_worker_process=json.loads((out / 'START.json').read_text(encoding='utf-8'))['process'],
        capture_process=guard,
        operation_sha256=hashlib.sha256((HERE / 'OPERATION.json').read_bytes()).hexdigest(),
        purpose='Exact installed local runtime; no claim of matching legacy pinned requirements',
        new_environment_START=0, new_training=0, new_fit=0)
    G.write_new(out / 'ENVIRONMENT.json', value)
    print(json.dumps({k: value[k] for k in ('python', 'numpy', 'torch', 'capture_commit')}))


if __name__ == '__main__':
    main()
