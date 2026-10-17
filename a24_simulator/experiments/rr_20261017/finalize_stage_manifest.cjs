// Manifest of the completed RR stage and fixed RL source preparation only.
// A live RL ledger/log/output is excluded rather than read while its writer runs.
const fs=require('fs'),path=require('path'),cp=require('child_process'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),file=path.join(root,'PACKAGE_MANIFEST.json'),m=JSON.parse(fs.readFileSync(file,'utf8'));
const excluded=p=>p.startsWith('results/RL_COST_20261017_01/')||p==='experiments/rl_cost_20261017/run.log';
const paths=cp.execFileSync('git',['ls-files','--cached','--others','--exclude-standard','-z','a24_simulator'],{cwd:path.dirname(root)}).toString('utf8').split('\0').filter(Boolean).map(p=>p.slice('a24_simulator/'.length)).filter(p=>p!=='PACKAGE_MANIFEST.json'&&!excluded(p));
const all=[...new Set(paths)],files=all.sort().map(p=>{const b=fs.readFileSync(path.join(root,p));return {path:p,sha256:crypto.createHash('sha256').update(b).digest('hex'),bytes:b.length}});
if(files.some(x=>x.bytes>=100*1024**2))throw Error('Oversize Git file');
m.files=files;m.total_bytes=files.reduce((s,x)=>s+x.bytes,0);m.build_scope='RR complete + frozen cost-RL source preparation; learning outputs are live and unpublished';
m.in_progress_exclusions=['results/RL_COST_20261017_01/','experiments/rl_cost_20261017/run.log'];
fs.writeFileSync(file,JSON.stringify(m,null,2)+'\n');console.log(JSON.stringify({files:files.length,bytes:m.total_bytes,scope:m.build_scope}));
