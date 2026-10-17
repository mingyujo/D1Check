"""Lossless compressed exact learner/experience snapshots, never auto-resume."""
import gzip,io,os
from pathlib import Path
import torch

def save_torch(path,value):
    buffer=io.BytesIO();torch.save(value,buffer)
    data=gzip.compress(buffer.getvalue(),compresslevel=1,mtime=0)
    with Path(path).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())

def load_torch(path):
    return torch.load(io.BytesIO(gzip.decompress(Path(path).read_bytes())),map_location='cpu',weights_only=False)

def save_snapshot(learner,path):save_torch(path,learner.snapshot())

def load_snapshot(learn,path):
    data=load_torch(path)
    if data['version']!=learn.VERSION or data['schema']!=learn.SCHEMA:raise ValueError('Exact checkpoint schema')
    actor=learn.Learner(data['seed'],data['family'],learn.Settings(**data['settings']))
    actor.net.load_state_dict(data['network']);actor.opt.load_state_dict(data['optimizer'])
    actor.action_rng.set_state(data['action_rng']);actor.shuffle_rng.set_state(data['shuffle_rng'])
    for key in ('duals','episodes','steps','updates','logs','pending','pending_meta'):setattr(actor,key,data[key])
    if learn.network_digest(actor.net)!=data['network_sha256']:raise ValueError('Network digest')
    return actor
