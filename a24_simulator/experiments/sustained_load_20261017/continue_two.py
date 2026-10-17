"""Finite duration comparison, preserving the complete frozen coupled model."""
from pathlib import Path
import gc,gzip,io,json,os,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ENTRY=Path(__file__).resolve()
sys.path.insert(0,str(ROOT/'experiments/coupled_345_20261017'))
from bootstrap import L,G,registration,public_input,save_binary,Nominal
from dynamics import Physics,Config
from controller import Controller
from engine import run as execute,metrics
from nn_train import Learner,digest
import torch
torch.set_num_threads(1)
G.OWN_TOKENS+=('sustained_load_20261017','coupled_345_20261017','savings_limit_20261017')
os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def saved(p,v):save_binary(p,gzip.compress(L.canonical(v).encode(),mtime=0))
def pt(p,v):
 b=io.BytesIO();torch.save(v,b);save_binary(p,gzip.compress(b.getvalue(),mtime=0))
def main():
 op=read(HERE/'CONTINUATION_OPERATION.json');opsha=L.sha(HERE/'CONTINUATION_OPERATION.json');out=ROOT/op['output_dir']
 L.need('--published' in sys.argv,'Registration must be published first')
 for p in [*op['sources'],*op['input_pins']]:L.pin(p)
 L.need(not out.exists(),'Consumed namespace: no automatic retry')
 guard=G.process_guard(ENTRY);volumes=G.free_guard([ROOT,'D:/'])
 import msvcrt
 lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
 count=0;rows=[];started=time.monotonic()
 try:
  out.mkdir();L.write_new(out/'START.json',dict(utc=L.now(),operation_sha256=opsha,guard=guard,volumes=volumes,
   HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),command=sys.argv,
   uncommitted_changes=bool(subprocess.check_output(['git','status','--porcelain']))))
  try:
   base,_,_=L.initialize(registration(op));catalog=read(L.pin(registration(op)['catalog_pin']))
   cost=read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json');physics=Physics(cost,Config(**op['physics']))
   snap=torch.load(io.BytesIO(gzip.decompress(Path(op['checkpoint']['path']).read_bytes())),map_location='cpu',weights_only=False)
   learner=Learner(op['learner_seed']);learner.restore(snap);before=digest(learner.net)
   action_rng=learner.action_rng.get_state().clone();shuffle_rng=learner.shuffle_rng.get_state().clone()
   counters=(learner.episodes,learner.updates,learner.steps)
   def simulate(case,mode,label,kind):
    nonlocal count
    G.process_guard(ENTRY);G.free_guard([ROOT,'D:/'])
    L.need(count<op['environment_cap'] and time.monotonic()-started<op['wall_clock_limit_s'],'Finite cap')
    receipt=dict(event='START',label=label,case=case['id'],kind=kind,policy=mode,utc=L.now(),
     identity=L.digest([opsha,label]),start_id=L.digest([opsha,label]),durable_START_consumed=True,operation_sha256=opsha)
    L.append(out/'receipts.jsonl',receipt);count+=1;print('START',count,label,'n',case['n'],flush=True)
    try:
     public,contexts=public_input(case,catalog);public['initial_ap_c']=case['temperature_c'];model=L.Model(base,contexts)
     actor=Controller(Nominal(model,public),physics,case,mode,learner if mode=='RL' else None,False)
     calls=0
     def progress(state):
      nonlocal calls
      calls+=1
      if calls%256==0:
       L.need(time.monotonic()-started<op['wall_clock_limit_s'],'Wall cap during dispatch')
       print('PROGRESS',label,'calls',calls,'sim_s',round(state['now_ns']/1e9-35,2),'queue',len(state['queue']),flush=True)
      return actor(state)
     result=execute(public,model,progress,physics,case['common_potential_key'],receipt);m=metrics(result,case,physics)
     raw=out/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls))
     frames=None
     if mode=='RL':
      frames=out/(label+'.frames.pt.gz');pt(frames,dict(frames=actor.frames,network_sha256=before,collect=False))
     row=dict(label=label,case=case['id'],kind=kind,policy=mode,n=case['n'],condition=case['condition'],metrics=m,
      raw_sha256=L.sha(raw),frames_sha256=L.sha(frames) if frames else None,network_sha256=before if mode=='RL' else None,measured_J=None)
     L.write_new(out/(label+'.json'),row);rows.append(row)
     L.append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','utc':L.now(),'raw_sha256':L.sha(raw),'result_sha256':L.sha(out/(label+'.json'))})
     print('COMPLETE',label,'on',m['on_time'],'/',m['planned'],'meanAP',round(m['mean_AP_c'],4),'elapsed',round(time.monotonic()-started,1),flush=True)
     del model,actor;gc.collect();return result
    except BaseException as exc:
     L.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','utc':L.now(),'error':str(exc),'automatic_retry':False});raise
   case=next(c for c in read(op['inputs']['path'])['cases'] if c['id']=='SUPPLY_600_1')
   for mode in ('ATC','RL'):
    result=simulate(case,mode,case['id']+'_'+mode,'SUSTAINED');del result;gc.collect()
   L.need(count==op['planned_START'],'Exact registered count')
   L.need(before==digest(learner.net) and counters==(learner.episodes,learner.updates,learner.steps),'No learning')
   L.need(torch.equal(action_rng,learner.action_rng.get_state()) and torch.equal(shuffle_rng,learner.shuffle_rng.get_state()),'No RNG consumption')
   for p in [*op['sources'],*op['input_pins']]:L.pin(p)
   L.write_new(out/'RESULT.json',dict(status='COMPLETED_RESEARCH_HYPOTHESIS',rows=rows,new_START=count,new_COMPLETE=count,new_FAIL=0,
    operation_sha256=opsha,network_sha256=before,counters=counters,network_and_training_RNG_unchanged=True,new_training=0,new_physical_fit=0,measured_J=None))
   L.write_new(out/'COMPLETE.json',dict(utc=L.now(),result_sha256=L.sha(out/'RESULT.json'),new_START=count,new_COMPLETE=count,elapsed_s=time.monotonic()-started))
  except BaseException as exc:
   L.write_new(out/'FAILURE.json',dict(utc=L.now(),error=str(exc),new_START=count,automatic_retry=False));raise
 finally:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
