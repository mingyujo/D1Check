"""Independent float64 NumPy actor calculation on saved evaluation banks."""
import gzip,hashlib,io,json,os
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import numpy as np
import torch
from nn_train import Net,digest
H=Path(__file__).resolve().parent;O=H/'artifacts/G001';op=json.loads((H/'OPERATION.json').read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
save(H/'NN_AUDIT_OPERATION.json',dict(scope='Independent NumPy actor and saved greedy decisions only; no environment/training',pins=[dict(path=str(p),sha256=sha(p)) for p in [Path(__file__),O/'RESULT.json',H/'OPERATION.json']]))
torch.set_num_threads(1)
result=json.loads((O/'RESULT.json').read_text(encoding='utf-8'));nets={};weights={};before={}
for seed in op['seeds']:
    p=Path(op['checkpoint_directory'])/f'S{seed}_FINAL.pt.gz';data=torch.load(io.BytesIO(gzip.decompress(p.read_bytes())),map_location='cpu',weights_only=False)['learner'];net=Net();net.load_state_dict(data['network']);net.temperature=data.get('temperature',.35);net.eval();nets[seed]=net;before[seed]=digest(net);weights[seed]={k:v.numpy().astype(np.float64) for k,v in net.state_dict().items()}
checks=0;decisions=0;ties=0;max_error=0.;cases=0
def need(condition,message):
    global checks
    checks+=1
    if not condition:raise AssertionError(message)
def check_batch(seed,frames):
    global decisions,ties,max_error
    w=weights[seed];net=nets[seed];x=np.asarray([f['bank']['x'] for f in frames],np.float32);mask=np.asarray([f['bank']['mask'] for f in frames],bool);xd=x.astype(np.float64)
    e=np.tanh(xd@w['encode.0.weight'].T+w['encode.0.bias']);mean=(e*mask[:,:,None]).sum(axis=1)/mask.sum(axis=1,keepdims=True).clip(1);maximum=np.where(mask[:,:,None],e,-1e9).max(axis=1);context=np.concatenate([mean,maximum],axis=-1)
    actor_input=np.concatenate([e,np.broadcast_to(context[:,None,:],(len(frames),27,96))],axis=-1);hidden=np.tanh(actor_input@w['actor.0.weight'].T+w['actor.0.bias']);manual=((hidden@w['actor.2.weight'].T+w['actor.2.bias']).squeeze(-1)/net.temperature);manual=np.where(mask,manual,-1e9)
    with torch.no_grad():actual,_=net(torch.from_numpy(x),torch.from_numpy(mask));actual=actual.numpy()
    error=np.max(np.abs(actual[mask]-manual[mask]));max_error=max(max_error,float(error));need(error<1e-4,'Independent actor logit tolerance')
    for i,frame in enumerate(frames):
        chosen=frame['index'];need(bool(mask[i,chosen]),'Physical action selected');decisions+=1
        m=int(manual[i].argmax());p=int(actual[i].argmax())
        if m!=chosen or p!=chosen:
            need(float(manual[i].max()-manual[i,chosen])<1e-4,'Manual reference action margin')
            with torch.no_grad():single,_=net(torch.from_numpy(x[i:i+1]),torch.from_numpy(mask[i:i+1]));exact=int(single[0].argmax())
            need(exact==chosen,'Exact original single-bank greedy action');ties+=1
        else:need(p==chosen,'Saved NN greedy action')
for row in result['rows']:
    if row['seed'] is None:need(row['neural_calls']==0 and row['network_sha256'] is None,'No NN in either pure rule');continue
    seed=row['seed'];need(row['network_sha256']==before[seed],'Correct fixed seed checkpoint');path=O/(row['label']+'.banks.jsonl.gz');need(sha(path)==row['banks_sha256'],'Bank trace SHA');batch=[];n=0
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:
            batch.append(json.loads(line));n+=1
            if len(batch)==128:check_batch(seed,batch);batch=[]
    if batch:check_batch(seed,batch)
    need(n==row['decisions'],'Complete NN decision coverage');cases+=1;print('FAIR_NN_AUDIT',cases,decisions,flush=True)
for seed,net in nets.items():need(digest(net)==before[seed],'No weights changed during evaluation audit')
need(cases==24,'All3 seeds x8 inputs audited')
proof=dict(status='PASS',cases=cases,decisions=decisions,checks=checks,independent_reference='float64 NumPy set encoder/mean/max pooling/actor from checkpoint tensors; exact single-bank torch fallback only within1e-4 numeric tie margin',numeric_tie_checks=ties,max_actor_logit_error=max_error,network_hashes=before,new_environment=0,new_training=0,new_optimizer_steps=0)
save(O/'NN_AUDIT.json',proof);print(json.dumps(proof))
