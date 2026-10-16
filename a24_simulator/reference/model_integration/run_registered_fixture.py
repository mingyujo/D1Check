"""Run only the exact registered local synthetic fixture module."""
import argparse
import importlib
import io
from pathlib import Path
import unittest
from runtime_guard import operation, pin, require, write_new, canonical

p=argparse.ArgumentParser();p.add_argument('--operation',required=True);args=p.parse_args()
with operation(args.operation,__file__) as (op,out):
    require(op['mode']=='ISOLATED_FIXTURE','Isolated fixture operation required')
    fixture=pin(op['fixture_pin'])
    require(fixture.parent.resolve()==Path(__file__).resolve().parent,'Local fixture only')
    require(fixture.name=='test_audit_lease.py','Registered fixture allowlist')
    require(any(x['sha256']==op['fixture_pin']['sha256'] and Path(x['path']).resolve()==fixture.resolve() for x in op['source_pins']),'Fixture not source pinned')
    for spec in op['fixture_closure_pins']:
        source=pin(spec)
        compile(source.read_bytes(),str(source),'exec')
    suite=unittest.TestLoader().loadTestsFromModule(importlib.import_module(fixture.stem))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    write_new(out/'TEST_RESULT.json',{'status':'PASS' if result.wasSuccessful() else 'FAIL','testsRun':result.testsRun,
        'output':stream.getvalue(),'errors':[(str(t),e) for t,e in result.errors],
        'failures':[(str(t),e) for t,e in result.failures],'new_environment':0,'real_process_job_setup':0,'new_fit':0,'HTTP':0})
    require(result.wasSuccessful(),'Registered fixture failed; retain output, no retry')
print(canonical({'status':'COMPLETE','output':str(out)}))
