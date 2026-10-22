"""Independent actor arithmetic and exact case-seeded categorical RNG replay."""
import gzip,hashlib,io,json,os
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import numpy as np,torch
from nn_train import Net,digest
H=Path(__file__).resolve().parent;O=H/'artifacts/G001';torch.set_num_threads(1)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):
 with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')
save(H/'NN_AUDIT_OPERATION.json',dict(scope='Independent float64 actor and exact saved stochastic action/RNG replay; no new plant/training',pins=[dict(path=str(p),sha256=sha(p)) for p in [Path(__file__),O/'RESULT.json',H/'OPERATION.json']]))
result=read(O/'RESULT.json');nets={};weights={};checks=0;decisions=0;fallbacks=0;max_error=0.;cases=0
def need(ok,msg):
 global checks
 checks+=1
 if not ok:raise AssertionError(msg)
def model(row):
 seed=row['seed'];ep=('BEFORE',row['label']) if row['kind']=='TRAIN' else 0 if row['method'].startswith('INITIAL_RL') else row['epoch'] if row['kind']=='DEV' else 'SELECTED';key=(seed,ep)
 if key not in nets:
  name=row['label']+'_before.pt.gz' if isinstance(ep,tuple) else f'S{seed}_SELECTED.pt.gz' if ep=='SELECTED' else f'S{seed}_EP{ep:03d}'+('_after.pt.gz' if ep else '.pt.gz')
  state=torch.load(io.BytesIO(gzip.decompress((O/name).read_bytes())),map_location='cpu',weights_only=False)
  net=Net();net.load_state_dict(state['network']);net.temperature=state.get('temperature',1.);net.eval();nets[key]=net;weights[key]={k:v.numpy().astype(np.float64) for k,v in net.state_dict().items()}
 return key
def batch(key,records,rng):
 global max_error,decisions,fallbacks
 net=nets[key];w=weights[key];x=np.asarray([f['bank']['x'] for f in records],np.float32);mask=np.asarray([f['bank']['mask'] for f in records],bool);xd=x.astype(np.float64)
 manual=3*np.tanh((np.tanh(xd)@w['weight'])/3)/net.temperature
 with torch.no_grad():actual,_=net(torch.from_numpy(x),torch.from_numpy(mask))
 err=float(np.max(np.abs(actual.numpy()[mask]-manual[mask])));max_error=max(max_error,err);need(err<1e-4,'Independent NumPy actor')
 probs=actual.log_softmax(-1).exp()
 for i,record in enumerate(records):
  before=rng.get_state().clone();chosen=int(torch.multinomial(probs[i],1,generator=rng));decisions+=1
  if chosen!=record['index']:
   rng.set_state(before)
   with torch.no_grad():single,_=net(torch.from_numpy(x[i:i+1]),torch.from_numpy(mask[i:i+1]));chosen=int(torch.multinomial(single.log_softmax(-1).exp()[0],1,generator=rng))
   fallbacks+=1
  need(chosen==record['index'] and bool(mask[i,chosen]),'Exact stochastic action and physical mask')
for row in result['rows']:
 if row['seed'] is None:need(row['neural_calls']==0 and row['network_sha256'] is None,'No NN in rolling rule');continue
 key=model(row);need(digest(nets[key])==row['network_sha256'],'Correct own fresh checkpoint')
 if row['kind']=='TRAIN':
  pre=torch.load(io.BytesIO(gzip.decompress((O/(row['label']+'_before.pt.gz')).read_bytes())),map_location='cpu',weights_only=False)
  collected=torch.load(io.BytesIO(gzip.decompress((O/(row['label']+'.frames.pt.gz')).read_bytes())),map_location='cpu',weights_only=False)['after_collect']
  expected=int(hashlib.sha256(f'{row["seed"]}|{row["stream"]}|CEM_TRAIN_CRN_V1'.encode()).hexdigest()[:16],16)%(2**63)
  need(row['train_rng_seed']==expected,'Registered CEM common random action seed')
  rng=torch.Generator().manual_seed(expected);end_rng_sha=hashlib.sha256(collected['action_rng'].numpy().tobytes()).hexdigest()
 else:
  expected=int(hashlib.sha256(f'{row["seed"]}|{row["stream"]}|DEPLOY_SAMPLE_V1'.encode()).hexdigest()[:16],16)%(2**63)
  need(expected==row['eval_rng_seed'],'Predeclared case-seeded evaluation RNG');rng=torch.Generator().manual_seed(expected);end_rng_sha=row['eval_rng_after_sha256']
 path=O/(row['label']+'.banks.jsonl.gz');need(sha(path)==row['banks_sha256'],'Saved bank SHA');records=[];count=0
 with gzip.open(path,'rt',encoding='utf-8') as f:
  for line in f:
   records.append(json.loads(line));count+=1
   if len(records)==128:batch(key,records,rng);records=[]
 if records:batch(key,records,rng)
 need(count==row['decisions'],'Complete stochastic decision census');need(hashlib.sha256(rng.get_state().numpy().tobytes()).hexdigest()==end_rng_sha,'Exact terminal collection/evaluation RNG')
 cases+=1;print('SAMPLED_NN_AUDIT',cases,decisions,flush=True)
 nets.clear();weights.clear()
need(cases==528,'All432TRAIN,48DEV and48 initial/trained EVAL neural cases')
save(O/'NN_AUDIT.json',dict(status='PASS',checks=checks,cases=cases,decisions=decisions,independent_reference='float64 NumPy encoder/pooling/actor plus exact case-seeded PyTorch categorical RNG replay',max_actor_logit_error=max_error,single_bank_float_rounding_fallbacks=fallbacks,new_environment=0,new_training=0,new_optimizer_steps=0))
print('SAMPLED_NN_AUDIT_PASS',checks,decisions,flush=True)
