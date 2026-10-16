"""Run the shipped high-contrast demonstration preset with one chosen policy."""
import argparse
import json
from pathlib import Path
import sys
from tools import d1_sched_landscape_cli as runtime
from tools import d1_sched_dynamics_policy as policy


def main():
    root=Path(__file__).resolve().parents[1]
    default=root/'demo_presets.json'
    if not default.exists():default=root.parent.parent/'outputs/D1-SCHED-RELLOAD-21/repro/demo_presets.json'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',choices=('A24','S26'),default='S26')
    parser.add_argument('--policy',choices=(*policy.RULES,'PPO'),default='ATC')
    parser.add_argument('--presets',type=Path,default=default)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    data=json.loads(args.presets.read_text(encoding='utf-8'));selected=data['presets'][args.device];bundle=args.presets.resolve().parent
    command=['d1_sched_landscape_cli','--profile',str(bundle/selected['profile']),'--requests',str(bundle/selected['requests']),
             '--policy',args.policy,'--environment-seed',str(selected['environment_seed']),'--out',str(args.out.resolve())]
    if args.policy=='PPO':command+=['--checkpoint',str(bundle/selected['checkpoint']),'--dependencies',str(bundle/selected['dependencies'])]
    sys.argv=command
    runtime.main()


if __name__=='__main__':main()
