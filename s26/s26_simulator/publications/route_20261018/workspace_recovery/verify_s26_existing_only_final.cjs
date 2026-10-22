'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process');
const R=path.resolve(__dirname,'../S26-D1Check'),S=path.join(R,'s26_simulator');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
const mpath=path.join(S,'LOCAL_EXTENSION_MANIFEST.json'),m=read(mpath);let files=0,bytes=0,links=0;
for(const f of m.files){const p=path.resolve(S,f.path);if(!p.startsWith(S+path.sep))throw Error('Snapshot path escaped');const st=fs.statSync(p);if(st.size!==f.bytes||sha(p)!==f.sha256)throw Error('Changed extension '+f.path);files++;bytes+=st.size;}
const core=path.join(S,'CORE_MANIFEST.json');if(sha(core)!==m.local_core_manifest_sha256)throw Error('Core overlay changed');
const parent=path.join(S,'docs/history/CORE_MANIFEST_G004_ORIGINAL_20261017.json');if(sha(parent)!==m.original_core_manifest_sha256)throw Error('Public original changed');
const report=path.join(S,'THERMAL_REPAIR_REPORT_KO_V3.md'),proof=read(path.join(S,'experiments/thermal_review_v3/REPORT_PROOF.json'));
if(sha(report)!==proof.report.sha256)throw Error('Report proof mismatch');
for(const match of fs.readFileSync(report,'utf8').matchAll(/\]\(([^)]+)\)/g)){const target=match[1];if(!target.startsWith('http')){if(!fs.existsSync(path.resolve(S,target)))throw Error('Broken report link '+target);links++;}}
const git=cp.execFileSync('git',['rev-parse','HEAD'],{cwd:R,encoding:'utf8'}).trim();if(git!==m.base_commit)throw Error('Unexpected HEAD');
const diff=cp.spawnSync('git',['diff','--check'],{cwd:R,encoding:'utf8'});if(diff.status!==0)throw Error('Diff check failed '+diff.stderr);
const coreVerification=JSON.parse(cp.execFileSync(process.execPath,['cli/s26.cjs','verify'],{cwd:S,encoding:'utf8'}));
if(coreVerification.status!=='PASS'||coreVerification.new_simulator_instances!==0)throw Error('Core verification failed');
const result={status:'PASS_SAVED_EXTENSION_AND_REPORT_INTEGRITY',utc:new Date().toISOString(),HEAD:git,working_tree:'UNCOMMITTED_LOCAL_CHANGES_NOT_UPLOADED',
 command:'node recovery/verify_s26_existing_only_final.cjs',extension_files:files,extension_bytes:bytes,report_local_links:links,
 original_core_manifest_sha256:sha(parent),local_core_manifest_sha256:sha(core),extension_manifest_sha256:sha(mpath),report_sha256:sha(report),core_verification:coreVerification,
 current_user_constraint:'Existing data only; no additional device measurement requested or performed',accuracy_gate_pass:false,adopted:false,
 new_policy_environment_instances_in_this_verification:0,new_fit_in_this_verification:0,new_RL:0};
const output=path.join(__dirname,'S26_EXISTING_ONLY_FINAL_VERIFICATION_20261018.json');fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(result));
