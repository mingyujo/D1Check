import json, glob, os
def sessions(tag):
    out=[]
    for d in sorted(glob.glob(f"/tmp/data/{tag}/*/")):
        if not os.path.exists(d+"device/progress.jsonl"): continue
        ev=[json.loads(l) for l in open(d+"device/progress.jsonl")]
        summ=json.load(open(d+"device/summary.json"))
        val=json.load(open(d+"validated.json")) if os.path.exists(d+"validated.json") else {}
        cb=json.load(open(d+"device/common_boundary.json"))
        hal=None
        if os.path.exists(d+"host/hal.csv"):
            import csv
            hal=list(csv.DictReader(open(d+"host/hal.csv")))
        out.append(dict(tag=tag,name=os.path.basename(d.rstrip('/')),ev=ev,summ=summ,val=val,cb=cb,hal=hal,dir=d))
    return out
