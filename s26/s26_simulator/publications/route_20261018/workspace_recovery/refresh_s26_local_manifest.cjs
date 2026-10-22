'use strict';
// Preserve the exact public G004 manifest and explicitly scope the local doc overlay.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../S26-D1Check/s26_simulator'),sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const current=path.join(root,'CORE_MANIFEST.json'),saved=path.join(root,'docs/history/CORE_MANIFEST_G004_ORIGINAL_20261017.json');
const parentSHA='7c94b6210ce229d44700f4014d04824de24e1983bc945d26925bff4aede4ed6c';
if(!fs.existsSync(saved)){
 const bytes=fs.readFileSync(current);if(sha(bytes)!==parentSHA)throw Error('Expected exact public manifest');
 fs.writeFileSync(saved,bytes,{flag:'wx'});
}
const bytes=fs.readFileSync(saved);if(sha(bytes)!==parentSHA)throw Error('Parent manifest changed');
const parent=JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/,'')),docs=new Set(['START_HERE.md','STATUS.md']),changes=[];
const files=parent.files.map(f=>{
 const raw=fs.readFileSync(path.join(root,f.path)),h=sha(raw);
 if(!docs.has(f.path)&&h!==f.sha256)throw Error('Unexpected parent scientific/core mutation '+f.path);
 if(h!==f.sha256)changes.push({path:f.path,parent_sha256:f.sha256,local_sha256:h});
 return {...f,bytes:raw.length,sha256:h};
});
const local={...parent,created_utc:new Date().toISOString(),scope:'Frozen G004 core file list; only START_HERE/STATUS docs updated for local extension. New experiment files are separately listed in LOCAL_EXTENSION_MANIFEST.json.',
 parent_manifest:{path:path.relative(root,saved).replaceAll('\\','/'),sha256:parentSHA},local_document_changes:changes,files};
fs.writeFileSync(current,JSON.stringify(local,null,2)+'\n');
const items=[];
function walk(dir){for(const f of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,f.name);if(f.isDirectory()){if(f.name!=='__pycache__')walk(p);}else if(f.isFile()){const b=fs.readFileSync(p);items.push({path:path.relative(root,p).replaceAll('\\','/'),bytes:b.length,sha256:sha(b)});}}}
for(const dir of ['sustained_load_v1','thermal_balance_v1','thermal_balance_v2','capacity_power_v1','pipeline_thermal_v1','thermal_review_v3','plain_edf_v1','a24_unprotected_v1','a24_unprotected_v2','a24_unprotected_v3','a24_load_margin_v1','a24_static_controls_v1','a24_repair_diagnosis_v1','a24_repair_diagnosis_v2','baseline_anchor_v1','energy_moment_v1','a24_policy_repair_v1','a24_stable_learning_v1'])walk(path.join(root,'experiments',dir));
for(const name of ['THERMAL_REPAIR_REPORT_KO.md','THERMAL_REPAIR_REPORT_KO_V2.md','THERMAL_REPAIR_REPORT_KO_V3.md','S26_A24_UNPROTECTED_RESULTS_KO.md','S26_A24_LOAD_MARGIN_RESULTS_KO.md','S26_FINAL_LOAD_COMPARISON_KO.md','S26_POLICY_REPAIR_RESULTS_KO.md','S26_POLICY_REPAIR_RESULTS_KO_V2.md','S26_POLICY_REPAIR_RESULTS_KO_V3.md','S26_STABLE_LEARNING_RESULTS_KO.md','S26_FINAL_DIAGNOSIS_KO.md']){const p=path.join(root,name);if(fs.existsSync(p)){const b=fs.readFileSync(p);items.push({path:name,bytes:b.length,sha256:sha(b)});}}
const extension={schema:'S26_LOCAL_EXTENSION_SNAPSHOT_V1',utc:new Date().toISOString(),base_commit:'b0b1c7df1775fcae3ba2944ed5df6d800382b4cc',
 original_core_manifest_sha256:parentSHA,local_core_manifest_sha256:sha(fs.readFileSync(current)),
 scope:'Local sustained-load, passive thermal, capacity-power, predicted-power pipeline, saved-review, plain EDF, A24-unprotected PPO and paired policy/physical repair including raw/failures/registrations/checkpoints; not uploaded. Runtime pycache omitted.',files:items.sort((a,b)=>a.path.localeCompare(b.path))};
fs.writeFileSync(path.join(root,'LOCAL_EXTENSION_MANIFEST.json'),JSON.stringify(extension,null,2)+'\n');
console.log(JSON.stringify({status:'LOCAL_MANIFEST_REFRESHED',preserved_parent_sha256:parentSHA,document_changes:changes,extension_files:items.length}));
