"""Independent saved NN/input/receipt/SHA audit, no simulation or updates."""
from pathlib import Path
import importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[2];ENTRY=Path(__file__).resolve()
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G
G.OWN_TOKENS+=('competition_cost_20261017','s26-state-aware-atc-','state_recovery_owner')
import numpy as np,torch
torch.set_num_threads(1)
def run(path):
    op=G.read(path);reg=G.read(ROOT/'models/registration.json');checks=0
    def need(q,s):
        nonlocal checks
        if not q:raise ValueError(s)
        checks+=1
    for p in op['source_pins']+op['input_pins']:G.pin(p)
    G.process_guard(ENTRY,reg['known_PS_producer_paths']);G.free_guard([ROOT,'D:/'])
    out=ROOT/op['output_dir'];need(not out.exists(),'Consumed audit output');out.mkdir(parents=True,exist_ok=False)
    G.write_new(out/'START.json',dict(operation_sha256=G.sha(path),utc=G.now()))
    try:
        spec=importlib.util.spec_from_file_location('competition_audit_learner',ROOT/'reference/rolling/learner.py')
        learn=importlib.util.module_from_spec(spec);sys.modules[spec.name]=learn;spec.loader.exec_module(learn)
        learner=learn.Learner.load_snapshot(G.pin(op['checkpoint']))
        witness=G.read(G.pin(op['witness_pin']));frames_total=0
        for case in witness['cases']:
            row=case['rows'][1];framepin=row['saved_frames'];frames=torch.load(G.pin(framepin),map_location='cpu',weights_only=False)
            need(len(frames)==len(row['protection_decisions']),'Frame/call alignment')
            for frame,decision in zip(frames,row['protection_decisions']):
                need(learn.input_digest(frame)==frame['input_sha']==decision['input_digest'],'Exact NN input digest')
                need(frame['time_ns']==decision['time_ns'] and frame['index']==decision['chosen_index'],'Public decision alignment')
                rp=learn.replay_frame(learner.net,frame)
                need(rp['argmax']==frame['index'],'Frozen argmax')
                need(abs(rp['logprob']-frame['old_logp'])<1e-6,'Log probability')
                need(np.allclose(rp['critic'],frame['value'],rtol=1e-5,atol=1e-6),'Critic')
                need(frame['mask'][frame['index']] and frame['physical_mask'][frame['index']],'Chosen legal action')
                need(np.array_equal(frame['mask'],decision['mask']),'Saved hierarchy mask')
                need(torch.equal(frame['action_rng_before'],frame['action_rng_after']),'No evaluation RNG consumed')
                need(not frame['collect'],'No NN collection or update')
                need(all(r['end_s']<=frame['time_ns']/1e9 for r in decision['public_state']['past_activity']),'No future owner history')
                frames_total+=1
            G.process_guard(ENTRY,reg['known_PS_producer_paths'])
        ledger=ROOT/'runtime/receipts.jsonl';ev=[json.loads(s) for s in ledger.read_text().splitlines() if s]
        counts={k:sum(e['event']==k for e in ev) for k in ('START','PREPARED','COMPLETE','FAIL')}
        need(counts['START']==406 and counts['COMPLETE']==403 and counts['FAIL']==3,'Shared child arithmetic')
        need(105+counts['START']==511,'Shared reservation arithmetic')
        starts=[r for r in ev if r['event']=='START'];need(len({r['identity'] for r in starts})==len(starts),'No duplicate START identity')
        recent=ROOT/'results/COMPETITION_WITNESS_V2_20261017_01'
        receipts=[json.loads(s) for s in (recent/'receipts.jsonl').read_text().splitlines() if s]
        for e in receipts:
            if e['event']=='PREPARED':
                need(G.sha(recent/(e['label']+'.raw.json.gz'))==e['raw_sha256'],'Prepared raw SHA')
                need(G.sha(recent/(e['label']+'.summary.json'))==e['summary_sha256'],'Prepared summary SHA')
        for p in reg['source_pins']+reg['input_pins']+op['source_pins']+op['input_pins']:G.pin(p)
        for p in ('WITNESS_V2_OPERATION.json','COST_OPERATION.json'):
            prior=G.read(ENTRY.with_name(p))
            for s in prior['source_pins']+prior['input_pins']:G.pin(s)
        saved=out/'SAVED_SHARED_RECEIPTS.jsonl';saved.write_bytes(ledger.read_bytes())
        G.write_new(out/'AUDIT.json',dict(status='PASS_SAVED_NN_INPUT_MASK_CRITIC_LOGPROB_ARGMAX_RNG_SHA_BUDGET',
                     checks=checks,eval_frames=frames_total,child_counts=counts,parent_START=105,
                     shared_START=511,shared_cap=512,remaining=1,source_sha256=G.sha(ENTRY),
                     portable_receipts_sha256=G.sha(saved),new_START=0,new_NN_training=0,measured_J=None,utc=G.now()))
        G.write_new(out/'COMPLETE.json',dict(audit_sha256=G.sha(out/'AUDIT.json'),utc=G.now()))
        print(json.dumps(dict(checks=checks,frames=frames_total,counts=counts)),flush=True)
    except BaseException as e:
        G.write_new(out/'FAILURE.json',dict(error=str(e),automatic_retry=False,utc=G.now()));raise
if __name__=='__main__':run(sys.argv[1])
