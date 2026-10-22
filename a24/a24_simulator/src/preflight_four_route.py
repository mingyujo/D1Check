"""Build/read-only numerical preflight, no scheduling environment or NN call."""
import copy,sys,os,json,math
from pathlib import Path
import lab_backend as lab
from timing_model import context_for_route
from four_route_model import conditional_energy
HERE=Path(__file__).resolve().parent
def main():
    lab.runtime_guard.process_guard(Path(os.environ['A24_LAB_GUARD_ENTRY']),[]);lab.free_guard([HERE,'D:/'])
    reg=lab.read(HERE.parent.parent/'outputs/A24-INTERACTIVE-POLICY-LAB-20261016-G004/REGISTRATION.json')
    base,thermal,profile=lab.initialize(reg);catalog=lab.read(lab.pin(reg['catalog_pin']))
    value={'requests':[{'ordinal':i,'profile':task+'_M128','priority':'U' if i==0 else 'N','arrival_s':35.,'deadline_s':37.} for i,task in enumerate(('C','D'))], 'seed':20261025,'rl_seed':46201,'alpha':.95,'initial_context':'M128'}
    public,contexts=lab.prepare_public(value,catalog['templates'],catalog['profiles']);model=lab.Model(base,contexts)
    nominal=[]
    for q in public['requests']:
        c,_=model.request_context(public,q)
        for route in ('CPU','GPU'):
            n=model.nominal(context_for_route(c,q['task'],route),q['task'],route,state={'queue_count':2,'initial_ap_c':public['initial_ap_c']})
            if not 0<=n['response_ns']<=n['occupancy_ns']:raise ValueError('Nominal four-route clocks')
            nominal.append({'task':q['task'],'route':route,**n})
    activity=copy.deepcopy(public);activity.update(activity_coverage_s=[0.,210.],observation_window_s=[0.,210.],owner_intervals=[{'request_id':'synthetic-CC','task':'C','route':'CPU','start_s':35.,'end_s':36.},{'request_id':'synthetic-DG','task':'D','route':'GPU','start_s':35.,'end_s':37.}])
    ap=lab.thermal_model.predict(thermal,activity,times=[0.,35.,36.,37.,180.],allow_extrapolation=True)
    if ap['status']!='CONDITIONAL_AP_PREDICTION' or not all(math.isfinite(x) for x in ap['ap_c']):raise ValueError('Four-route AP numeric preflight: '+str(ap))
    energy=conditional_energy(activity,profile,0.,180.)
    if not math.isfinite(energy['historical_conditional_J']):raise ValueError('Four-route cost preflight')
    out=Path(sys.argv[1]);out.mkdir(exist_ok=False)
    lab.write_new(out/'FOUR_ROUTE_MODELS.json',{'thermal':thermal,'profile':profile,'timing':model.metadata,'ratios':model.ratios})
    lab.write_new(out/'RESULT.json',{'status':'PASS_NUMERICAL_PREFLIGHT','nominal':nominal,'synthetic_AP':ap,'synthetic_energy':energy,'new_environment':0,'NN_inference':0,'new_training':0,'parameter_fit':0,'utc':lab.now()})
    lab.write_new(out/'COMPLETE.json',{'result_sha256':lab.sha(out/'RESULT.json'),'models_sha256':lab.sha(out/'FOUR_ROUTE_MODELS.json')})
    print(json.dumps({'status':'PASS_NUMERICAL_PREFLIGHT','four_route_nominal_ns':[{k:r[k] for k in ('task','route','response_ns','occupancy_ns')} for r in nominal],'new_environment':0}))
if __name__=='__main__':main()
