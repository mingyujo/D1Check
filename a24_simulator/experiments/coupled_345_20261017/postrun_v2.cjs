'use strict';
// One explicit saved-only verification stage per invocation; no automatic retry.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir);
const stages={
 audit:{entry:'audit_v2.py',outputs:['AUDIT.json']},
 metrics:{entry:'audit_metrics.cjs',outputs:['SAVED_METRIC_AUDIT.json']},
 summary:{entry:'summarize.cjs',outputs:['ANALYSIS.json']},
 choices:{entry:'choice_diagnostics.cjs',outputs:['CHOICE_DIAGNOSTICS.json']},
 goals:{entry:'goal_checks.cjs',outputs:['GOAL_CHECKS.json']},
 figures:{entry:'figures.py',outputs:['POLICY_COMPARISON.png','FIXED_HOT_CASE_GANTT.png','FIGURES.json']},
 environment_v2:{entry:'capture_environment_v2.py',outputs:['ENVIRONMENT.json']},
 pins:{entry:'verify_pins.cjs',outputs:['SOURCE_PIN_VERIFICATION.json']}
};
const name=process.argv[2],stage=stages[name];if(!stage)throw Error('Choose one registered verification stage');
if(!fs.existsSync(path.join(out,'COMPLETE.json')))throw Error('Completed experiment required');
const driver=read(path.join(__dirname,'POSTRUN_DRIVER_OPERATION_V2.json'));
if(driver.source.sha256!==sha(__filename))throw Error('Registered driver bytes changed');
const log=path.join(out,'verification_receipts.jsonl');
const previous=fs.existsSync(log)?fs.readFileSync(log,'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse):[];
if(previous.some(x=>x.stage===name)||stage.outputs.some(p=>fs.existsSync(path.join(out,p))))throw Error('Preserve consumed verification stage; repair separately');
const python=stage.entry.endsWith('.py');
const executable=python?'C:\\Users\\user\\anaconda3\\python.exe':process.execPath;
const args=[path.join(__dirname,stage.entry)];
const revision=cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim();
const dirty=cp.execFileSync('git',['status','--porcelain'],{cwd:repo,encoding:'utf8'}).length>0;
const common={stage:name,executable,args,HEAD:revision,uncommitted_changes:dirty,
 entry_sha256:sha(args[0]),driver_sha256:sha(__filename),new_environment_START:0,new_fit:0};
const append=x=>fs.appendFileSync(log,JSON.stringify({...common,utc:new Date().toISOString(),...x})+'\n');
append({event:'VERIFY_BEGIN'});
const child=cp.spawnSync(executable,args,{cwd:repo,stdio:'inherit',env:{...process.env,
 OMP_NUM_THREADS:'1',MKL_NUM_THREADS:'1',
 PYTHONPYCACHEPREFIX:path.join(root,'.cache/coupled345_pycache'),
 MPLCONFIGDIR:path.join(root,'.cache/coupled345_mpl')}});
const status=child.status===null?1:child.status;
append({event:status===0?'VERIFY_COMPLETE':'VERIFY_FAIL',exit_code:status,error:child.error?String(child.error):null,
 outputs:stage.outputs.filter(p=>fs.existsSync(path.join(out,p))).map(p=>({path:p,sha256:sha(path.join(out,p)),bytes:fs.statSync(path.join(out,p)).size}))});
process.exitCode=status;
