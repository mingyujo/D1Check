"""Read trusted frozen checkpoint metadata only; no policy/model/environment execution."""
import gzip,hashlib,io,json,os
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import numpy as np
import torch
W=Path(__file__).resolve().parents[1];S=W/'S26-D1Check/s26_simulator';G=S/'experiments/route_group_learning_v1';P=G/'artifacts/G001'
items={}
for key,name in [('selected','S881087_FINAL.pt.gz'),('BC_control','BC_COMMON_FINAL.pt.gz')]:
 p=P/name;d=torch.load(io.BytesIO(gzip.decompress(p.read_bytes())),map_location='cpu',weights_only=False);s=d['learner'];h=hashlib.sha256()
 for n,t in sorted(s['network'].items()):h.update(n.encode());h.update(t.detach().numpy().tobytes())
 assert h.hexdigest()==s['network_sha256']
 items[key]=dict(path=p.relative_to(S).as_posix(),file_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size,seed=s['seed'],network_sha256=h.hexdigest(),network_parameters=sum(t.numel() for t in s['network'].values()),checkpoint_ABI=s['version'],temperature=s.get('temperature',1),episodes=s['episodes'],PPO_updates=s['updates'],balance=d['balance'])
evidence=dict(status='PASS_READ_ONLY_FROZEN_CHECKPOINT_METADATA',items=items,new_policy_forward_calls=0,new_environment=0,new_training=0,new_fits=0)
p=W/'recovery/S26_FINAL_CANDIDATE_INSPECTION.json'
with p.open('x',encoding='utf-8') as f:json.dump(evidence,f,indent=2)
print(json.dumps(evidence))
