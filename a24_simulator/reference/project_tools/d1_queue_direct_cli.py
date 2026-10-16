"""Guarded entry point; supplements the historical __main__ source-lock omission."""
import argparse,json
from pathlib import Path
from tools import d1_queue_direct_study as study

def guard(folder):
    reg=study.check(folder)
    key=Path(study.__file__).resolve().relative_to(study.ROOT).as_posix()
    expected=reg['sources'].get(key)
    if expected is None:
        receipt=study.budget.read(folder/'driver_freeze_receipt.json')
        if receipt['registration_sha256']!=study.budget.digest(folder/'registration.json') or receipt['path']!=key:
            raise ValueError('supplemental driver identity mismatch')
        expected=receipt['sha256']
    if study.budget.digest(study.__file__)!=expected:raise ValueError('frozen study driver changed')
    return reg

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','check','run'));p.add_argument('--run-root',type=Path,required=True);p.add_argument('--stop-after',type=int)
    x=p.parse_args();folder=x.run_root
    if x.command=='register':
        # This implementation has one explicitly reserved fixed seed contract.
        # Repeating it under a new directory is not an independent confirmation.
        if any(study.budget.read(v).get('task')==study.budget.TASK for v in folder.parent.glob('*/registration.json')):
            raise ValueError('fixed-seed task already registered; resume it or explicitly revise the next seed contract')
        r=study.register(folder)
        # Imported study is present under tools.* and hence included in sources().
        guard(folder)
    else:
        r=guard(folder)
        if x.command=='run':r=study.run(folder,x.stop_after)
        else:r=dict(status='PASS_source_driver_and_input_guard',task=r['task'],completed=study.budget.read(folder/'cursor.json')['completed'])
    print(json.dumps(study.serial(r),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
