"""Reproduce only the published raw-free suite/demo, charged to the new task."""
import argparse
import functools
import json
import platform
import sys
import unittest
from pathlib import Path

from tools import d1_atc_pilot_budget as ledger

SUITE = (
    "tools.test_d1_simulation_model_v2", "tools.test_d1_simulation_model_v2_campaign",
    "tools.test_d1_simulation_model_v2_report", "tools.test_d1_simulation_model_v3",
    "tools.test_d1_simulation_model_v3_campaign", "tools.test_d1_simulation_model_v3_energy",
    "tools.test_d1_simulation_model_v3_prediction", "tools.test_d1_simulation_model_v3_thermal",
)
PRIVATE = (
    "tools.test_d1_simulation_model_v3_inputs", "tools.test_d1_simulation_model_v3_report",
    "tools.test_d1_simulation_model_v3_hybrid_report",
)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-root",required=True,type=Path)
    parser.add_argument("stage",choices=("portable_suite","frozen_demo"))
    args=parser.parse_args(); b=ledger.Budget(args.run_root)
    path=args.run_root/(args.stage+".json")
    if path.exists():raise FileExistsError("completed preflight evidence retained; no automatic rerun")
    from tools import d1_simulation_model_v2 as m
    from tools import d1_list_candidate_rl_engine as engine
    from tools import d1_arrival_explore as old_engine
    from tools import d1_simulation_model_v2_demo as demo
    import numpy,torch,matplotlib
    originals=[];count=0
    def wrap(module):
        nonlocal count
        original=module.simulate;originals.append((module,original))
        @functools.wraps(original)
        def call(*a,**kw):
            nonlocal count
            if b._depth:return original(*a,**kw)
            count+=1
            with b.environment(f"preflight_{args.stage}_{count}",args.stage):
                return original(*a,**kw)
        module.simulate=call
    for module in (m,engine,old_engine):wrap(module)
    try:
        with b.session():
            if args.stage=="portable_suite":
                tests=unittest.defaultTestLoader.loadTestsFromNames(SUITE)
                result=unittest.TextTestRunner(verbosity=2).run(tests)
                evidence=dict(status="PASS" if result.wasSuccessful() else "FAIL",
                    tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                    private_raw_required=list(PRIVATE),private_suites_executed=False)
            else:
                result=demo.demo(m.ROOT/"docs/results/simulation_model_v2_01/run_v1/model.json",
                                 args.run_root/"frozen_demo",mode="mean")
                evidence=dict(status="PASS",result=result)
            evidence.update(environment_invocations=count,consumption=b.used(),
                python=platform.python_version(),numpy=numpy.__version__,torch=torch.__version__,
                matplotlib=matplotlib.__version__,device_commands=0,
                scope="published raw-free functionality; no historical raw refit reproduction")
            ledger.write(path,evidence)
    finally:
        for module,original in originals:module.simulate=original
    print(json.dumps(evidence,ensure_ascii=False,default=str))
    if evidence["status"]!="PASS":raise SystemExit(1)


if __name__=="__main__":main()
