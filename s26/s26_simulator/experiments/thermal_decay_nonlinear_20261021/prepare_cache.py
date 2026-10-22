"""Precompute and pin causal features once; no new fit is run in preparation."""
from pathlib import Path
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import json,gzip,importlib.util,sys,hashlib,time
import numpy as np
H=Path(__file__).resolve().parent;R=H.parents[2];E=H.parent;C=H/'input_cache';assert not C.exists();C.mkdir()
sys.stdout.reconfigure(encoding='utf-8')
spec=importlib.util.spec_from_file_location('registered_linear_preparation',E/'thermal_decay_refinement_20261021/fit.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
from features import design
begin=time.monotonic();entries=old.prepare();groups,pm,tm,paths=old.load_models();arrays={};metadata=[];err=0
for j,e in enumerate(entries):
    pub=e['public'];base,X=design(pub,pm[e['group']],tm[e['group']]);err=max(err,float(max(abs(base-e['old']))))
    for key in ['B','activity','drift']:arrays[f'{j}_{key}']=pub[key]
    metadata.append(dict(id=e['id'],group=e['group'],pool=e['pool'],cohort=e['cohort'],times=e['times'].tolist(),observed=e['observed'].tolist(),old=e['old'],public={k:v for k,v in pub.items() if k not in ['B','activity','drift','times']}))
assert err<1e-7
with (C/'arrays.npz').open('xb') as f:np.savez_compressed(f,**arrays)
(C/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False),encoding='utf-8')
paths=[H/'PROTOCOL.json',H/'features.py',Path(__file__),E/'thermal_decay_refinement_20261021/fit.py',E/'pipeline_thermal_v1/OPERATION.json',E/'pipeline_thermal_v1/artifacts/G001/OOF_ROWS.json.gz',E/'thermal_balance_v1/artifacts/G001/PREPARED.json.gz',E/'multiresource_v1/calibration/MATERIALIZED_SESSIONS.json.gz',C/'arrays.npz',C/'metadata.json',*paths]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pre=dict(status='PASS_PRE_FIT_CAUSAL_CACHE',sessions=208,points=25975,baseline_max_reconstruction_error_C=err,input_dimension=40,feature_map='Same39 causal features + frozen base T. No future measured AP/power.',source=[dict(path=p.relative_to(R).as_posix(),sha256=sha(p)) for p in paths],elapsed_s=time.monotonic()-begin,new_fit_START=0)
(H/'PREFLIGHT.json').write_text(json.dumps(pre,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in pre.items() if k!='source'},ensure_ascii=False),flush=True)
