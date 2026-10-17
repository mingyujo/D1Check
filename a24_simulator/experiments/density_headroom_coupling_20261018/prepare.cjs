'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const pin=p=>({path:p,sha256:sha(p),bytes:fs.statSync(p).size}),save=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const parent=path.join(root,'experiments/density_headroom_20261018/OPERATION.json'),op=read(parent),out=path.join(root,op.output_dir);
if(read(path.join(out,'RESULT.json')).new_COMPLETE!==82||read(path.join(out,'AUDIT.json')).status!=='PASS')throw Error('Original native diagnosis must complete and audit first');
const ast=read(path.join(__dirname,'AST_RESULT.json'));if(ast.status!=='PASS')throw Error('Source-only checks first');
for(const p of ast.sources)if(sha(p.path)!==p.sha256)throw Error('Source check no longer binds current bytes');
const source=['coupling.py','run.py','audit.cjs','report.cjs','prepare.cjs','pure.cjs','phase.cjs','all_deadline.cjs','README.md'].map(f=>pin(path.join(__dirname,f)));
const generated=fs.readdirSync(out).filter(f=>/BANK|CERT|raw\.json\.gz|RESULT|BOUNDS|COMPLETE|AUDIT|EVALUATION|SUMMARY|ALL_ROWS|REPORT|PROOF/.test(f)).map(f=>pin(path.join(out,f)));
const dedup=a=>[...new Map(a.map(p=>[p.path.toLowerCase(),p])).values()];
save(path.join(__dirname,'OPERATION.json'),{schema:'A24-density-headroom-coupled-saved-only-v1',utc:new Date().toISOString(),base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),
 parent_operation:pin(parent),sources:dedup([...op.sources,...source]),input_pins:dedup([...op.input_pins,...generated,pin(parent),pin(path.join(__dirname,'PURE_TEST_RESULT.json')),pin(path.join(__dirname,'AST_RESULT.json'))]),
 physics:op.physics,original_thermal_upper_c:op.thermal_upper_c,parent_output:op.output_dir,output_dir:'results/DENSITY_HEADROOM_COUPLED_20261018_01',
 new_environment_START:0,new_global_reservation:0,existing_unused6_untouched:true,LP_solves:40,LP_seconds:15,
 frozen_bank_restores:0,new_physical_fit:0,new_training:0,new_device_actions:0,automatic_retry:false,
 refinement:'Necessary heat/work exposure constraints, nonpreemptive phase-burst thermal barrier and deposition endpoint bounds; no coefficient, input, timing, or schedule change',
 all_original112_rows_preserved:true,exclusion_reasons_preserved:true,all_old_and_new40_bound_rows_displayed:true,
 all_on_time_capacity_check:'Saved analytic cold response-prefix two-lane demand on fixed24x24 intervals, no LP/native',
 own_Python_limit:1,global_Python_limit:2,min_free_GiB:8,wall_clock_limit_s:1800,node_executable:'C:/Program Files/nodejs/node.exe'});
console.log(JSON.stringify({status:'REGISTERED_SAVED_ONLY',new_environment:0,new_reservation:0,LP:40}));
