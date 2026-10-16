const fs=require('fs'),path=require('path'),cp=require('child_process'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),file=path.join(root,'PACKAGE_MANIFEST.json'),m=JSON.parse(fs.readFileSync(file,'utf8'));
const paths=cp.execFileSync('git',['ls-files','--cached','--others','--exclude-standard','-z','a24_simulator'],{cwd:path.dirname(root)}).toString('utf8').split('\0').filter(Boolean).map(p=>p.slice('a24_simulator/'.length)).filter(p=>p!=='PACKAGE_MANIFEST.json');
const all=[...new Set(paths)],order=m.files.map(x=>x.path),extra=all.filter(p=>!order.includes(p)).sort(),files=[];
for(const p of [...order,...extra]){if(!all.includes(p))continue;const b=fs.readFileSync(path.join(root,p));files.push({path:p,sha256:crypto.createHash('sha256').update(b).digest('hex'),bytes:b.length});}
if(files.some(x=>x.bytes>=100*1024**2))throw Error('Oversize Git file; archive separately');
m.files=files;m.total_bytes=files.reduce((s,x)=>s+x.bytes,0);fs.writeFileSync(file,JSON.stringify(m,null,2)+'\n');
console.log(JSON.stringify({files:files.length,bytes:m.total_bytes,appended:extra.length,max_file_bytes:Math.max(...files.map(x=>x.bytes))}));
