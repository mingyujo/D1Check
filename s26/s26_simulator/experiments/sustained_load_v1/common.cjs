'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),zlib=require('node:zlib');
const HERE=__dirname,ROOT=path.resolve(HERE,'../..'),WORKSPACE=path.resolve(ROOT,'../..');
const packetPath=path.join(ROOT,'experiments/multiresource_v1/PACKET.json.gz');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const read=p=>{const b=fs.readFileSync(p);return JSON.parse((p.endsWith('.gz')?zlib.gunzipSync(b):b).toString('utf8').replace(/^\uFEFF/,''));};
function write(file,value){const data=Buffer.from(JSON.stringify(value)+'\n'),fd=fs.openSync(file+'.part','wx');try{fs.writeFileSync(fd,data);fs.fsyncSync(fd)}finally{fs.closeSync(fd)}fs.renameSync(file+'.part',file);}
function binary(file,data){const fd=fs.openSync(file+'.part','wx');try{fs.writeFileSync(fd,data);fs.fsyncSync(fd)}finally{fs.closeSync(fd)}fs.renameSync(file+'.part',file);}
const pin=p=>({path:p,bytes:fs.statSync(p).size,sha256:sha(fs.readFileSync(p))});
function verify(op){for(const f of op.pins)if(sha(fs.readFileSync(f.path))!==f.sha256)throw Error('Pin changed '+f.path);}
function p0Cases(){const old=path.join(ROOT,'archive/multiresource/outputs/S26-MULTIRESOURCE-20261017-G004/PRODUCTION'),rows=fs.readFileSync(path.join(old,'ROWS.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);return rows.filter(r=>r.phase==='EVAL'&&r.config.capacity===3&&r.config.bank==='MIX'&&r.config.burst===16&&r.config.context_index===0&&r.config.draw===0&&['LOW','CENTRAL'].includes(r.config.model)).map(r=>({id:'P0_'+r.config.model+'_'+r.config.policy,kind:'P0',n:128,duration_s:16,old_raw:path.join(old,'raw',r.logical_identity+'.json.gz'),config:{...r.config,horizon_s:180,dispatch_stop_s:120,censor_s:150,forecast_cap:5000,nominal_event_cap:20000}}));}
function baseline(packet,scenario){const m=packet.power,b=scenario.context.initial_context.targets.POWER_API.baseline.median_api_w;return (1-m.mean[0])/m.scale[0]*m.coef[0]+(b-m.mean[1])/m.scale[1]*m.coef[1];}
// Continuous-time closed form for positive additive box and exponential tails.
function energy(packet,scenario,activity,a,b){const m=packet.power;if(m.mean.some(x=>x!==0))throw Error('Nonzero means need explicit treatment');let J=baseline(packet,scenario)*(b-a);const ramp=t=>t<=0?0:t<.5?t*t: t-.25;
 for(let k=0;k<9;k++)for(const [l,r,w] of activity[k]){
  const box=t=>w*(ramp(t-l)-ramp(t-r));J+=(box(b)-box(a))*m.coef[2+k]/m.scale[2+k];
  for(const [index,tau] of [1,10,60].entries()){const primitive=t=>t<=l?0:t<=r?w*((t-l)+tau*Math.expm1(-(t-l)/tau)):w*((r-l)-tau*(Math.exp(-(t-r)/tau)-Math.exp(-(t-l)/tau)));const j=11+index*9+k;J+=(primitive(b)-primitive(a))*m.coef[j]/m.scale[j];}
 }return J;}
module.exports={fs,path,zlib,HERE,ROOT,WORKSPACE,packetPath,sha,read,write,binary,pin,verify,p0Cases,baseline,energy};
