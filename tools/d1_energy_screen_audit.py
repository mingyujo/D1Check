"""PC-only existing receipts analysis. Never invokes ADB or writes source artifacts."""
import argparse
import csv
import json
import statistics
from pathlib import Path

def audit(root):
    rows=[];all_rows=[]
    for path in sorted((Path(root)/'host_commands').glob('*/client/result.json')):
        r=json.loads(path.read_text());all_rows.append(r)
        if r['command'][-3:]!=['shell','dumpsys','power']:continue
        raw=(path.parent/'stdout.bin').read_bytes()
        rows.append(dict(command_id=path.parent.parent.name,status=r['status'],utc_start=r['utc_start'],
            seconds=r['elapsed_seconds'],stdout_bytes=len(raw),stderr_bytes=r['stderr_bytes'],
            start=r['monotonic_start'],end=r['monotonic_end'],
            partial_awake=b'mWakefulness=Awake' in raw,
            partial_interactive=b'mHalInteractiveModeEnabled=true' in raw,
            # Offline filtering only; no claim about on-device execution time.
            selected_state_bytes=sum(len(l)+1 for l in raw.splitlines() if
                l.strip().startswith((b'mWakefulness=',b'mHalInteractiveModeEnabled=')))))
    good=[r for r in rows if r['status']=='returned'];times=sorted(r['seconds'] for r in good)
    return rows,dict(screen_queries=len(rows),completed=len(good),failed=len(rows)-len(good),
        successful_seconds=dict(min=min(times),median=statistics.median(times),max=max(times),
            p95_nearest_rank=times[__import__('math').ceil(.95*len(times))-1]),
        successful_bytes=dict(min=min(r['stdout_bytes'] for r in good),median=statistics.median(r['stdout_bytes'] for r in good),max=max(r['stdout_bytes'] for r in good)),
        selected_state_bytes=sorted({r['selected_state_bytes'] for r in rows}),
        recorded_client_overlaps=sum(b['monotonic_start']<a['monotonic_end'] for a,b in zip(all_rows,all_rows[1:])),
        same_screen_start_gaps_seconds=[b['start']-a['start'] for a,b in zip(rows,rows[1:])],
        basis='observed old single session, not predictive distribution or new device validation')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    rows,summary=audit(a.run);out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    with (out/'screen_queries.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
