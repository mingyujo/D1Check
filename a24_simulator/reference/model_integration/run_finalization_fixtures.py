"""Run one exact saved-auditor/UI boundary fixture module under the shared lock."""
import argparse
import importlib
import io
from pathlib import Path
import unittest
from runtime_guard import canonical,operation,pin,require,write_new

def main():
    p=argparse.ArgumentParser();p.add_argument('--operation',required=True);args=p.parse_args()
    with operation(args.operation,__file__) as (op,out):
        require(op['mode']=='ISOLATED_FINALIZATION_FIXTURES','Exact isolated fixture operation')
        fixture=pin(op['fixture_pin'])
        require(fixture.parent.resolve()==Path(__file__).resolve().parent and fixture.name in
                ('test_audit_forecast_results.py','test_report_ui_lease.py'),'Exact new fixture allowlist')
        require(any(Path(s['path']).resolve()==fixture.resolve() and s['sha256']==op['fixture_pin']['sha256'] for s in op['source_pins']),'Fixture source pin')
        compiled=[]
        for source in op['source_pins']:
            path=pin(source)
            if path.suffix=='.py':compile(path.read_bytes(),str(path),'exec');compiled.append(str(path))
        suite=unittest.TestLoader().loadTestsFromModule(importlib.import_module(fixture.stem))
        stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        write_new(out/'TEST_RESULT.json',{'status':'PASS' if result.wasSuccessful() else 'FAIL','testsRun':result.testsRun,
            'output':stream.getvalue(),'compiled':compiled,'new_environment':0,'new_fit':0,'NN':0,
            'real_browser':0,'real_process_job':0,'raw_access':0,'HTTP':0})
        require(result.wasSuccessful(),'Fresh fixture failed; retain output and do not retry')
    print(canonical({'status':'COMPLETE','output':str(out)}))
if __name__=='__main__':main()
