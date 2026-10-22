"""Additive mean baseline and an independently scaled state head; target-free prediction."""
import importlib.util,math
import numpy as np
from common import PH
spec=importlib.util.spec_from_file_location('_energy01_dynamics',PH/'energy_model.py');prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
STATES=prior.STATES;SCHEMA='A24-additive-absolute-energy-v2'
SETTINGS=[{'background':b,'tau_s':t,'total_weight':w} for b in ['flat','context'] for t in [0.,.9,10.,30.] for w in [.5,.9]]
def context(c,windows,kind,reference):
    pre=c['pre_mean'];delta=c['pre_delta'];a=np.array([x-35 for x,y in windows]);b=np.array([y-35 for x,y in windows]);dt=b-a
    if kind=='flat':return np.full((len(windows),1),pre/reference)
    decay=60*(np.exp(-a/60)-np.exp(-b/60))/dt
    return np.column_stack([pre/reference*(1-decay),(1-pre/reference)*(1-decay),delta/reference*decay])
def design(c,windows,setting,reference):return np.column_stack([context(c,windows,setting['background'],reference),prior.design(c,windows,setting['tau_s'])[:,1:]])
def bounds(setting):return (np.array([-.3,*([0.,-.25] if setting['background']=='context' else []),*([0.]*4)]),np.array([.3,*([.5,.25] if setting['background']=='context' else []),*([4.]*4)]))
def predict_source_mean(c,windows,m):
    if m['kind']=='PRE_MEDIAN':return np.full(len(windows),c['pre_power'])
    if m['kind']=='PRE_MEAN':return np.full(len(windows),c['pre_mean'])
    if m['kind']=='V1':return prior.predict_mean(c,windows,m['prior_model'])*c['pre_power']
    return c['pre_mean']+m['reference_power']*design(c,windows,m,m['reference_power'])@np.array(m['coefficients'])
def constant(kind):return {'kind':kind,'schema':SCHEMA,'training_sessions':[],'training_groups':[]}
def source_energy(c,windows,m):return predict_source_mean(c,windows,m)*np.array([b-a for a,b in windows])
