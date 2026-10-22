"""Audit-only exact-kernel cache, with original direct-kernel golden checks."""
import collections,hashlib,importlib.util,json,math,os,sys
from pathlib import Path
import numpy as np

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 op=json.loads(Path(os.environ['S26_UNIFIED_OPERATION']).read_text(encoding='utf-8-sig'));O=Path(op['output_dir']).parent
 sys.path.insert(0,str(Path(op['original_audit_entry']).parent))
 audit=load('state_original_audit',op['original_audit_entry']);import state_replay as sr
 old=load('original_direct_kernel_cache_reference',op['original_direct_math']);original_predict=sr.predict;original_duration=sr.duration
 cache=collections.OrderedDict();stats=collections.Counter();refs={};duration_cache={}
 def duration_cached(model,row,AP,overlap,variant='CENTRAL'):
  refs[id(model)]=model;refs[id(row)]=row;key=(id(model),id(row),float(AP),float(overlap),variant)
  if key not in duration_cache:duration_cache[key]=original_duration(model,row,AP,overlap,variant);stats['duration_misses']+=1
  else:stats['duration_hits']+=1
  return duration_cache[key]
 class Adapter:
  @staticmethod
  def filtered_activity(segments,times,beta,start):
   t=np.asarray(times,dtype=float);lo=float(np.min(t));hi=float(np.max(t));done=[];pending=[]
   for xs in segments:
    a=[];b=[]
    for l,r,w in xs:
     l=max(start,l);r=max(l,r)
     if l>=hi or r<=l:continue
     (a if r<=lo else b).append((l,r,w))
    done.append(a);pending.append(b)
   key=(float(beta),float(start),lo,tuple(tuple(xs) for xs in done))
   if key in cache:z=cache[key];cache.move_to_end(key);stats['past_state_hits']+=1
   else:
    z=old.filtered_activity(done,np.array([lo]),beta,start)[0];z.flags.writeable=False;cache[key]=z;stats['past_state_misses']+=1
    if len(cache)>2048:cache.popitem(last=False)
   return np.exp(-beta*(t-lo))[:,None]*z[None,:]+old.filtered_activity(pending,t,beta,start)
  @staticmethod
  def windowed_activity(segments,times,width,start):
   if width==0:return old.windowed_activity(segments,times,width,start)
   t=np.asarray(times,dtype=float);lo=float(np.min(t));hi=float(np.max(t));trim=[[(l,r,w) for l,r,w in xs if r>lo-width and max(start,l)<hi] for xs in segments]
   return old.windowed_activity(trim,t,width,start)
 def fast_predict(model,segments,ctx,times,direct):return original_predict(model,segments,ctx,times,Adapter)
 # Independent original functions are called on fixed saved inputs, before any full replay.
 rows=[json.loads(l) for l in (O/'PRODUCTION/ROWS.jsonl').read_text().splitlines() if l.strip()];packet=json.loads(Path(op['packet_path']).read_text());eq=0;maxerr=0.
 for row in rows[::25]:
  r=json.loads(Path(row['raw_path']).read_text());nom=r['public_nominal_model']
  for d in (r['policy_decisions'][0],r['policy_decisions'][-1]):
   obs=d['public_observation'];state=obs['cost_state'];ts=np.array(sorted({state['targets']['AP']['anchor'].get('time_s',state['targets']['AP']['anchor'].get('t_s')),obs['sensor']['time'],obs['time'],obs['time']+.05,obs['time']+.5,obs['time']+3,90.,180.}))
   for model in (packet['AP'],packet['power']):
    a=original_predict(model,state['activity9']['intervals'],state['targets'],ts,old);b=fast_predict(model,state['activity9']['intervals'],state['targets'],ts,old);err=float(np.max(abs(a-b)));maxerr=max(maxerr,err);assert err<1e-10,('golden kernel mismatch',err);eq+=1
   for route in ('classification_CPU','classification_GPU','classification_NPU','detection_CPU'):
    n=nom['routes'][route];a=original_duration(nom['timing'],n['identity'],obs['sensor']['AP'],0);b=duration_cached(nom['timing'],n['identity'],obs['sensor']['AP'],0);assert a==b;eq+=1
  # Forecast-shaped future query, including intervals that continue beyond its first query.
  obs=r['policy_decisions'][0]['public_observation'];sr.MODELS=packet;sr.DIRECT=old
  gold=sr.forecast(obs,nom,'detection_CPU','normal');sr.predict=fast_predict;cached=sr.forecast(obs,nom,'detection_CPU','normal');sr.predict=original_predict
  for k in gold:err=abs(gold[k]-cached[k]);maxerr=max(maxerr,err);assert err<1e-10;eq+=1
 proof=dict(status='PASS',checks=eq,max_abs_error=maxerr,original_function_objects_preserved=True,new_policy_environments=0,new_NN=0,new_fit=0)
 with (O/'FAST_KERNEL_EQUIVALENCE.json').open('x',encoding='utf-8') as f:json.dump(proof,f,indent=2)
 sr.predict=fast_predict;sr.duration=duration_cached
 import audit_resource_v2 as resource
 resource.duration=duration_cached
 # Same independently implemented audit body, new output/operation only.
 audit.main(op)
 with (O/'FAST_KERNEL_CACHE_STATS.json').open('x',encoding='utf-8') as f:json.dump(dict(stats),f,indent=2)
if __name__=='__main__':main()
