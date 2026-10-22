'use strict';
const fs=require('fs'),zlib=require('zlib'),crypto=require('crypto');
function network(p,expected){
 const b=zlib.gunzipSync(fs.readFileSync(p)),e=b.lastIndexOf(Buffer.from([0x50,0x4b,0x05,0x06]));
 if(e<0)throw Error('ZIP end');let pos=b.readUInt32LE(e+16);const files=new Map();
 for(let i=0;i<b.readUInt16LE(e+10);i++){
  if(b.readUInt32LE(pos)!==0x02014b50)throw Error('ZIP directory');
  const method=b.readUInt16LE(pos+10),size=b.readUInt32LE(pos+20),nl=b.readUInt16LE(pos+28),el=b.readUInt16LE(pos+30),cl=b.readUInt16LE(pos+32),offset=b.readUInt32LE(pos+42),name=b.subarray(pos+46,pos+46+nl).toString();
  const start=offset+30+b.readUInt16LE(offset+26)+b.readUInt16LE(offset+28),data=b.subarray(start,start+size);
  files.set(name,method===0?data:method===8?zlib.inflateRawSync(data):null);pos+=46+nl+el+cl;
 }
 const names=['encode.0.weight','encode.0.bias','actor.0.weight','actor.0.bias','actor.2.weight','actor.2.bias','critic.0.weight','critic.0.bias','critic.2.weight','critic.2.bias'];
 const sizes=[48*40,48,64*144,64,64,1,64*96,64,5*64,5],net={},buffers={};
 for(let i=0;i<names.length;i++){
  const key=[...files.keys()].find(k=>k.endsWith('/data/'+i)),data=files.get(key);
  if(!data||data.length!==sizes[i]*4)throw Error('Float32 tensor storage '+i);
  buffers[names[i]]=data;net[names[i]]=Float64Array.from({length:sizes[i]},(_,j)=>data.readFloatLE(j*4));
 }
 const h=crypto.createHash('sha256');for(const n of names.slice().sort()){h.update(n);h.update(buffers[n]);}
 const digest=h.digest('hex');if(digest!==expected)throw Error('Exact full network tensor/name digest mismatch');
 return {net,digest,tensors:names.length,extraction:'Storage order accepted only after exact original network digest matches; no pickle executed'};
}
function dense(x,w,b,out,tanh=false){const y=new Float64Array(out);for(let i=0;i<out;i++){let s=b[i],start=i*x.length;for(let j=0;j<x.length;j++)s+=w[start+j]*x[j];y[i]=tanh?Math.tanh(s):s;}return y;}
function logits(net,x,mask){
 const enc=x.map(a=>dense(a,net['encode.0.weight'],net['encode.0.bias'],48,true)),mean=new Float64Array(48),max=new Float64Array(48).fill(-Infinity),n=mask.filter(Boolean).length;
 for(let a=0;a<35;a++)if(mask[a])for(let j=0;j<48;j++){mean[j]+=enc[a][j]/n;max[j]=Math.max(max[j],enc[a][j]);}
 return enc.map((e,i)=>{if(!mask[i])return -Infinity;const xx=new Float64Array(144);xx.set(e);xx.set(mean,48);xx.set(max,96);const hidden=dense(xx,net['actor.0.weight'],net['actor.0.bias'],64,true);return dense(hidden,net['actor.2.weight'],net['actor.2.bias'],1)[0];});
}
module.exports={network,logits};
if(require.main===module){const r=JSON.parse(fs.readFileSync('a24_simulator/results/SUSTAINED_LOAD_REPORT_20261017_01/RESULT.json')),p=JSON.parse(fs.readFileSync(__dirname+'/OPERATION.json')).checkpoint.path;const n=network(p,r.network_sha256);console.log(JSON.stringify({status:'PASS',network_sha256:n.digest,tensors:n.tensors}));}
