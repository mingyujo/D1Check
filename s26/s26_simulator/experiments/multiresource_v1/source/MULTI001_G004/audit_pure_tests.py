"""Independent math, timing, activity, and adversarial fixtures; no sampled environment."""
import importlib.util,json,math,subprocess
from pathlib import Path
import numpy as np
W=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('audit_fixture_module',W/'multi_audit.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
def run(op):
 p=a.read(op['packet_path']);q=json.loads(subprocess.check_output([op['node_path'],str(W/'audit_fixture_queries.cjs'),op['packet_path']],creationflags=subprocess.CREATE_NO_WINDOW));maxAP=0;maxP=0;maxRate=0
 for f in q['fixtures']:
  ap=a.predict(p['AP'],f['ints'],f['targets'],f['ts']);power=a.predict(p['power'],f['ints'],f['targets'],f['ts']);maxAP=max(maxAP,float(np.max(np.abs(ap-f['AP']))));maxP=max(maxP,float(np.max(np.abs(power-f['power']))));a.test(np.allclose(ap,f['AP'],rtol=0,atol=1e-8),'independent AP fixtures');a.test(np.allclose(power,f['power'],rtol=0,atol=1e-8),'independent power fixtures '+repr((maxP,power.tolist(),f['power'])))
 for f in q['rates']:
  model=p['multi']['models'][f['model']];log=a.timing_log(p,f['identity'],f['AP'],model)+math.log(f['residual'])
  for peer in f['peers']:
   known='detection_CPU' in (f['route'],peer['route']) and any(r in ('classification_GPU','classification_NPU') for r in (f['route'],peer['route']))
   if known:
    m=p['timing'];k=m['spec']['labels'].index('OVERLAP:'+f['route']);log+=m['coef'][k]+(1.645*m['bootstrap_sd'][k] if model['measured_beta_variant']=='HIGH_SLOPE' else 0)
   else:log+=model['unknown_beta']
  rate=math.exp(-log);maxRate=max(maxRate,abs(rate-f['rate']));a.close(rate,f['rate'],'independent route-rate fixture')
 for s,value in q['seeds']:a.test(a.seed(s)==value,'independent sample RNG')
 # Hand-written two resource phases with an inferred shared CPU prefix and passive gap.
 s=p['scenarios'][0];ints=[[x[:] for x in xs] for xs in s['context']['pre_activity9']['intervals']];phases=[(35,'GAP',.01,0),(35.01,'ADMISSION',.02,.01),(35.03,'INFER',0,0),(35.08,'RETURN_GAP',.01,0),(35.09,'POST',.02,.01)]
 for channel,l,r in [(7,35,35.01),(4,35.01,35.03),(2,35.03,35.08),(7,35.08,35.09),(5,35.09,35.11),(6,35,35.11)]:ints[channel].append([l,r,1])
 raw={'scenario':s['id'],'config':{'model':'CENTRAL','capacity':3},'activity':ints,'phase_trace':[dict(time=t,event='ENTER',ordinal=0,route='classification_GPU',phase=ph,wall_duration_s=wall,cpu_service_s=cpu) for t,ph,wall,cpu in phases]+[dict(time=35.11,event='AVAILABLE',ordinal=0,route='classification_GPU')],'cpu_intervals':[dict(start=35.01,end=35.02,ordinal=0,route='classification_GPU',phase='ADMISSION'),dict(start=35.09,end=35.10,ordinal=0,route='classification_GPU',phase='POST')],'right_censored_at150':False,'shared_cpu_wait_s':0,'active_at_censor':[]}
 a.phase_service_audit(raw);a.activity_audit(p,raw);raw['activity'][2][-1][2]=2;detected=False
 try:a.activity_audit(p,raw)
 except AssertionError:detected=True
 a.test(detected,'activity corruption rejected')
 return dict(status='PASS',checks=a.checks,AP_max_error=maxAP,power_max_error=maxP,rate_max_error=maxRate,cost_fixtures=len(q['fixtures']),rate_fixtures=len(q['rates']),new_policy_environments=0,new_Simulator=0,new_fit=0)
