'use strict';
const fs=require('node:fs'),path=require('node:path'),H=path.resolve(__dirname,'../S26-D1Check/s26_simulator/experiments/a24_load_margin_v1'),P=path.resolve(H,'../a24_unprotected_v3');
if(fs.existsSync(path.join(H,'run.py')))throw Error('Runner already prepared');
let s=fs.readFileSync(path.join(P,'run.py'),'utf8');
const a=s.indexOf("    inputs=read(HERE/'INPUTS.json')"),b=s.indexOf("    engine=subprocess.Popen",a);
s=s.slice(0,a)+[
 "    inputs=read(HERE/'INPUTS.json')['cases'];cases={'EVAL':inputs}",
 "    started=time.monotonic();count=0;rows=[];selection=None;counter={'BANK':0,'deadline_guard_observed':0};learners={};update_audits=[];training_stats={}"
].join('\n')+'\n'+s.slice(b);
const start=s.indexOf("        assert read(out/'P0.json')"),end=s.indexOf('        assert count==',start);if(start<0||end<0)throw Error('Parent execution block not found');
const block=[
 "        parent=Path(op['parent_output']);assert (parent/'FINAL_PROOF.json').exists(),'Parent audits/report must finish first'",
 "        selected_record=read(parent/'SELECTION_FROZEN.json');selected=selected_record['per_seed'];chosen_seed=selected_record['primary_seed'];shutil.copyfile(parent/'SELECTION_FROZEN.json',out/'SELECTION_FROZEN.json');selection=sha(out/'SELECTION_FROZEN.json')",
 "        for seed in op['seeds']:",
 "            learner=Learner(seed);snap=torch.load(io.BytesIO(gzip.decompress((parent/f'S{seed}_EP{selected[str(seed)]:03d}.pt.gz').read_bytes())),map_location='cpu',weights_only=False);learner.restore(snap);learners[seed]=learner",
 "        before_network={seed:digest(l.net) for seed,l in learners.items()}",
 "        for i,c in enumerate(cases['EVAL']):",
 "            for mode in ('EDF','EDF_NPU_FIRST','ATC','EXACT'):simulate(c,mode,f'MARGIN_{i}_{mode}','EVAL')",
 "            for seed in op['seeds']:simulate(c,'RL',f'MARGIN_{i}_S{seed}','EVAL',learners[seed])",
 "        assert all(digest(l.net)==before_network[seed] for seed,l in learners.items()),'Evaluation changed frozen NN'"
].join('\n')+'\n';s=s.slice(0,start)+block+s.slice(end);
s=s.replace('len(rows)==527','len(rows)==56').replace('imported_prior_operational_FAIL=1,imported_prior_nominal_TRAIN_FAIL=1,combined_START=count+10,combined_COMPLETE_receipts=count+8,combined_FAIL=2,','additional_training=0,').replace("row=dict(label=label,kind=kind,input=case['id'],","row=dict(label=label,kind=kind,input=case['id'],nominal_load_ratio=case['nominal_load_ratio'],nominal_capacity_requests_s=case['nominal_capacity_requests_s'],").replace('CONDITIONAL_UNPROTECTED_A24_TO_S26_COMPLETE','CONDITIONAL_LOAD_MARGIN_COMPARISON_COMPLETE');
fs.writeFileSync(path.join(H,'run.py'),s,{flag:'wx'});
let nn=fs.readFileSync(path.join(P,'audit_nn.py'),'utf8');const x=nn.indexOf('    train_cases='),y=nn.indexOf('    nets={}',x);nn=nn.slice(0,x)+nn.slice(y);nn=nn.replace("out/f'S{seed}_EP{ep:03d}.pt.gz'","Path(op['parent_output'])/f'S{seed}_EP{ep:03d}.pt.gz'").replace("check(update_replays==191,'Full training update count');check(result['START']==518 and result['combined_START']==528,'Expected new generation')","check(update_replays==0,'No new training');check(result['START']==56,'Expected new margin generation')");
fs.writeFileSync(path.join(H,'audit_nn.py'),nn,{flag:'wx'});fs.copyFileSync(path.join(P,'audit_saved.cjs'),path.join(H,'audit_saved.cjs'));
console.log('MARGIN_RUNNER_AND_SAVED_AUDIT_PREPARED_NO_EXECUTION');
