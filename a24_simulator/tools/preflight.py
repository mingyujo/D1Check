from pathlib import Path
import sys,json,os
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'src'))
import lab_backend as L
def main():
 reg=L.read(P/'models/registration.json')
 model,thermal,profile=L.initialize(reg)
 catalog=L.read(L.pin(reg['catalog_pin']))
 v={'requests':[{'profile':'C_M128','priority':'U','arrival_s':35.,'deadline_s':37.2},{'profile':'D_M128','priority':'N','arrival_s':35.5,'deadline_s':40.5}],'seed':20261101,'rl_seed':46201,'initial_context':'M128','alpha':.95}
 v=L.validate_input(v,catalog['profiles'])
 public,contexts=L.prepare_public(v,catalog['templates'],catalog['profiles']);m=L.Model(model,contexts)
 import numpy,torch
 assert m.metadata['model_digest']==reg['expected_four_route_timing_digest']
 assert thermal['model_sha256']==reg['expected_four_route_AP_sha256']
 L.write_new(P/'models/PREFLIGHT.json',{'status':'PASS_EXACT_ORIGINAL_MODELS_RELOCATED','timing':m.metadata,'AP_sha256':thermal['model_sha256'],'numpy':numpy.__version__,'torch':torch.__version__,'environment_START':0,'NN_training':0})
 print('PASS: portable exact model construction; numpy',numpy.__version__,'torch',torch.__version__)
if __name__=='__main__':main()
