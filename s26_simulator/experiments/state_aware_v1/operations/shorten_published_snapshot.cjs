'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');const O=__dirname,B=path.resolve(O,'../..'),D=path.join(B,'work/S26-GITHUB-HANDOFF-20261016/repository/s26_simulator/experiments/state_aware_v1/operations'),root=path.resolve(D,'source_snapshot');
const read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,'')),sha=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
const manifest=read(path.join(D,'MANIFEST.json')),map=read(path.join(D,'SOURCE_MAP.json')),mapping=new Map(),destRecords=new Map();
fs.mkdirSync(path.join(D,'sources'),{recursive:true});
for(const r of manifest.files.filter(x=>x.path.startsWith('source_snapshot/'))){
 const old=path.resolve(D,r.path);if(!old.startsWith(root+path.sep)||sha(old)!==r.sha256)throw Error('Generated snapshot boundary/hash');
 const ext=path.extname(old),name=path.basename(old,ext).slice(0,30)+'__'+r.sha256.slice(0,12)+ext,rel='sources/'+name,dest=path.resolve(D,rel);
 if(!dest.startsWith(path.resolve(D,'sources')+path.sep))throw Error('Destination boundary');
 if(fs.existsSync(dest)){if(sha(dest)!==r.sha256)throw Error('Alias collision');fs.unlinkSync(old)}else fs.renameSync(old,dest);
 if(sha(dest)!==r.sha256)throw Error('Moved source bytes changed');mapping.set(r.path,rel);destRecords.set(rel,{path:rel,bytes:r.bytes,sha256:r.sha256});
}
for(const r of map){const dest=mapping.get(r.snapshot_path);if(!dest)throw Error('Unmapped source');r.snapshot_path=dest}
manifest.files=[...manifest.files.filter(x=>!x.path.startsWith('source_snapshot/')),...destRecords.values()];
fs.writeFileSync(path.join(D,'MANIFEST.json'),JSON.stringify(manifest,null,2)+'\n');fs.writeFileSync(path.join(D,'SOURCE_MAP.json'),JSON.stringify(map,null,2)+'\n');
const actual=find=>map.find(x=>x.original_path.replace(/\\/g,'/').endsWith(find))?.snapshot_path;
const readme=path.join(D,'README_KO.md');let text=fs.readFileSync(readme,'utf8');
text=text.replace('source_snapshot/outputs/S26-STATE-AWARE-ATC-20261016/AUDIT_SOURCE/audit_state_full.py',actual('AUDIT_SOURCE/audit_state_full.py'));
text=text.replace('source_snapshot/outputs/S26-STATE-AWARE-ATC-20261016/FAST_AUDIT_SOURCE_V2/fast_audit_runner.py',actual('FAST_AUDIT_SOURCE_V2/fast_audit_runner.py'));
text=text.replace('source_snapshot/outputs/S26-STATE-AWARE-ATC-20261016/RECOVERY_SOURCE_V2/','sources/ 아래의 SOURCE_MAP 원경로 RECOVERY_SOURCE_V2 대응 파일');
text+='\nWindows 긴 경로의 Git 색인 오류를 방지하도록 운영 소스 복사본만 sources/의 짧은 이름으로 포장했다. 원 source/운영 등록/소스 바이트는 변경하지 않았고, SOURCE_MAP이 원경로·SHA·짧은 포장경로를 연결한다. 파일 이동은 이번에 생성한 배포 복사본 안에서만 수행했다.\n';fs.writeFileSync(readme,text);
const proof={status:'PASS',reason:'Portable packaging only: preserve source bytes with shorter relative names after Git Windows filename-too-long staging rejection.',source_bindings:map.length,unique_source_files:destRecords.size,renamed_files:[...mapping].map(([from,to])=>({from,to})),original_work_and_output_source_changes:0};
fs.writeFileSync(path.join(D,'PORTABLE_SOURCE_LAYOUT.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx'});fs.copyFileSync(__filename,path.join(D,'shorten_published_snapshot.cjs'),fs.constants.COPYFILE_EXCL);console.log(JSON.stringify({status:'PASS',source_bindings:map.length,source_files:destRecords.size}));
