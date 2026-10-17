import json
for s in (46101,46103,46107):
    L=[json.loads(x) for x in open(f'runs/seed{s}/train_log.jsonl')]
    g=[r for r in L if r['load']['kind']=='GEN']
    def m(rs): return round(sum(100*r['on_time']/r['planned'] for r in rs)/max(1,len(rs)),1)
    rt=lambda rs,k: sum(r['routes'][k] for r in rs)
    tot=lambda rs: max(1,sum(rt(rs,'classification_'+x) for x in ('CPU','GPU','NPU')))
    print(s, len(L), 'gen on-time first40', m(g[:40]), 'last40', m(g[-40:]), 'upd', L[-1]['updates'], 'NPU last40', round(rt(g[-40:],'classification_NPU')/tot(g[-40:]),2), 'wait last40', round(sum(r['wait_s'] for r in L[-40:]),2), 'wall', L[-1]['wall'])
