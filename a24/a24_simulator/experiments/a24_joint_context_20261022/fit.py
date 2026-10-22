import time
import numpy as np
from common import *
from model import *
from lp import solve

class Study:
    def __init__(self,data):self.data=data;self.cs={c['session']:c for c in data['cases']};self.bases=Bases();self.memo={};self.count=0;self.selections=[]
    def log(self,row):
        with (O/'FIT_LEDGER.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(row,allow_nan=False,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
    def base(self,ids,setting,head,label):
        b=self.bases.get(ids,setting,head);self.log({'event':'EXACT_BASE_REUSE','id':label,'head':head,'source_id':b['identity'],'training_sessions':ids});return b
    def fit(self,ids,base,setting,head,identity):
        key=(head,base_key(ids,base,head),json.dumps(setting,sort_keys=True))
        if key in self.memo:self.log({'event':'REUSE_NEW','id':identity,'source_id':self.memo[key]['identity']});return self.memo[key]
        resources();self.count+=1;assert self.count<=600;begun=time.time();self.log({'event':'START','id':identity,'index':self.count,'head':head,'training_sessions':ids})
        try:
            cs=[self.cs[s] for s in ids];stats=statistics(cs,head,setting);x,y,w,g,lim=train_arrays(cs,head,base,setting,stats);lo,hi=bounds(stats,head);beta,cert=solve(x,y,w,lo,hi,setting['ridge'],g,lim)
            m={'schema':SCHEMA,'head':head,'base':base,'setting':setting,'statistics':stats,'coefficients':beta.tolist(),'training_sessions':ids,'training_groups':sorted({c['group'] for c in cs}),'identity':identity,'family':cs[0]['family']}
            with (O/'FIT_CERTIFICATES.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'id':identity,**cert},allow_nan=False,separators=(',',':'))+'\n')
            self.memo[key]=m;self.log({'event':'COMPLETE','id':identity,'index':self.count,'elapsed_s':time.time()-begun,'model':m});return m
        except BaseException as e:self.log({'event':'FAIL','id':identity,'error':repr(e),'automatic_retry':False});raise
    def zero(self,ids,base,head,identity):return {'schema':SCHEMA,'head':head,'base':base,'setting':None,'statistics':None,'coefficients':[],'training_sessions':ids,'training_groups':sorted({self.cs[s]['group'] for s in ids}),'identity':identity,'family':self.cs[ids[0]]['family']}
    def select(self,ids,setting,head,identity):
        allrows=[[] for j in range(9)];receipts=[]
        for k,held in enumerate(split([self.cs[s] for s in ids],3)):
            tr=[s for s in ids if self.cs[s]['group'] not in held];te=[s for s in ids if self.cs[s]['group'] in held];base=self.base(tr,setting,head,f'{identity}/INNER{k}/BASE');receipts.append({'fold':k,'training_sessions':tr,'held_sessions':te,'base_identity':base['identity']})
            zero=self.zero(tr,base,head,f'{identity}/INNER{k}/BASE');allrows[0].extend(metrics([self.cs[s] for s in te],zero,head))
            for j,st in enumerate(SETTINGS[head]):
                m=self.fit(tr,base,st,head,f'{identity}/INNER{k}/C{j}');allrows[j+1].extend(metrics([self.cs[s] for s in te],m,head))
        scores=[score(r,head) for r in allrows];ok=[0]+[j for j in range(1,9) if eligible(scores[j],scores[0],head)];winner=min(ok,key=lambda j:(scores[j]['MAE'],j));record={'id':identity,'head':head,'training_sessions':ids,'inner':receipts,'winner_index':winner,'candidates':[{'index':j,'setting':None if j==0 else SETTINGS[head][j-1],'eligible':j in ok,**s} for j,s in enumerate(scores)]};self.selections.append(record)
        base=self.base(ids,setting,head,identity+'/FINAL_BASE');return self.zero(ids,base,head,identity+'/ZERO') if winner==0 else self.fit(ids,base,SETTINGS[head][winner-1],head,identity+'/SELECTED')

def main():
    d=read(O/'INPUTS.json');reg=read(O/'REGISTRATION.json');check_sources(reg);s=Study(d);pred=[]
    for family in ['old','m8']:
        ids=[c['session'] for c in d['cases'] if c['family']==family]
        for k,held in enumerate(d['outer_groups'][family]):
            tr=[i for i in ids if s.cs[i]['group'] not in held];te=[i for i in ids if s.cs[i]['group'] in held];ms={h:s.select(tr,d['base_settings'][f'{family}/{k}'][h],h,f'{family}/OUTER{k}/{h}') for h in ['T','E']};write(O/f'{family}_OUTER_{k}.json',{'models':ms,'held_groups':held,'held_sessions':te})
            for sid in te:
                c=s.cs[sid];assert all(c['group'] not in ms[h]['training_groups'] for h in ms);ws=[(w['lo'],w['hi']) for w in c['eval_windows']];tw=[(w['lo'],w['hi']) for w in c['train_windows']];pred.append({'session':sid,'family':family,'group':c['group'],'outer_fold':k,'models':ms,'temperature':predict_t(c,ms['T']).tolist(),'eval_relative_mean_power':(predict_e(c,ws,ms['E'])/c['pre_power']).tolist(),'ten_second_relative_mean_power':(predict_e(c,tw,ms['E'])/c['pre_power']).tolist()})
            print(json.dumps({'state':'OUTER_COMPLETE','family':family,'fold':k,'fits':s.count,'settings':{h:ms[h]['setting'] for h in ms}}),flush=True)
        write(O/f'{family}_DEPLOYMENT_MODELS.json',{h:s.select(ids,d['base_settings'][f'{family}/DEPLOYMENT'][h],h,f'{family}/DEPLOYMENT/{h}') for h in ['T','E']})
    write(O/'INNER_SELECTIONS.json',s.selections);write(O/'OOF_PREDICTIONS.json',pred);write(O/'FIT_COMPLETE.json',{'fits':s.count,'fit_limit':600,'fit_failures':0,'cases':len(pred),'new_measurements':0,'policy_environments':0,'fresh_confirmation':False});check_sources(reg);print(json.dumps({'state':'FIT_COMPLETE','fits':s.count,'cases':len(pred)}),flush=True)
if __name__=='__main__':main()
