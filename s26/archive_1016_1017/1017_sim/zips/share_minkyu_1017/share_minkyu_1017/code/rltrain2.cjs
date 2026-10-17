// Rolling+ATC+RL (ATC-guided residual linear policy), self-critical policy gradient. Physics/coefficients untouched except the declared virtual-device k.
const fs=require('fs'),zlib=require('zlib'),path=require('path');const simdir=process.argv[2],mode=process.argv[3];
const {Simulator}=require(path.join(simdir,'src/s26_simulator_v2.cjs'));
const packet=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(simdir,'data/engine_packet.json.gz'))));
const orig=packet.timing.coef.slice();function setK(k){packet.timing.coef=orig.map((c,j)=>packet.timing.spec.labels[j].startsWith('AP:')?c*k:c);}
const W=JSON.parse(fs.readFileSync('W.json'));
eval(fs.readFileSync('run3.cjs','utf8').match(/function makeRequests[\s\S]*?\n}\n/)[0]);
function mulberry(a){return()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
const NF=15;
function run(wid,ctx,stream,k,rl){setK(k);const base=packet.scenarios.find(s=>s.id===ctx);const sc={...base,requests:makeRequests(W[wid]),policy:'ROLLING_ATC_ROUTE_V2',policy_args:null};
 const r=new Simulator(packet,sc,{policy:'ROLLING_ATC_ROUTE_V2',stream,action_options:{classification_routes:['classification_CPU','classification_GPU','classification_NPU'],allow_wait:false,rl}}).run();
 return {on:r.service.all.on_time,n:r.service.all.planned,u:r.service.urgent.on_time,J:r.J_API0_180??0,AP:r.AP35_180_mean,unf:r.unfinished};}
const score=o=>o.on-0.02*o.J;
const TRAIN=JSON.parse(process.argv[4]),KS=[2,4,8],CTX=['R1-4-M128_BASE','R2-3-M128_BASE','R3-1-M128_BASE'],DEVS=[260016200,260016201,260016202,260016203];
if(mode==='sanity'){const th=[60,...Array(NF-1).fill(0)];console.log(JSON.stringify(run('D25_g0.65_c5d3_B','R1-4-M128_BASE',260016200,1,{theta:th,sample:false})));process.exit(0);}
let th=[+(process.env.TH0||3),...Array(NF-1).fill(0)];const rand=mulberry(+(process.env.SEED||20261017)),lr=+process.argv[5],EP=+process.argv[6];const log=[];
const devEval=()=>{let s=0;for(const w of TRAIN)for(const c of CTX)for(const st of DEVS.slice(0,2))for(const k of KS)s+=score(run(w,c,st,k,{theta:th,sample:false}));return s;};
let best={s:devEval(),th:th.slice(),ep:0};console.error('ep0 dev',best.s.toFixed(1));log.push({ep:0,dev:best.s});
for(let ep=1;ep<=EP;ep++){
 const w=TRAIN[Math.floor(rand()*TRAIN.length)],c=CTX[Math.floor(rand()*CTX.length)],st=DEVS[Math.floor(rand()*DEVS.length)],k=KS[Math.floor(rand()*KS.length)];
 const g0=score(run(w,c,st,k,{theta:th,sample:false}));
 const trace=[];const o=run(w,c,st,k,{theta:th,sample:true,rand,trace});const A=(score(o)-g0)/o.n*100;
 const g=Array(NF).fill(0);for(const t of trace){const f=t.F[t.k];for(let i=0;i<NF;i++){let e=0;for(let j=0;j<t.F.length;j++)e+=t.P[j]*t.F[j][i];g[i]+=f[i]-e;}}
 const nrm=Math.max(1,trace.length);for(let i=0;i<NF;i++)th[i]+=lr*A*g[i]/nrm;
 if(ep%50===0){const s=devEval();log.push({ep,dev:s,th:th.slice()});console.error('ep',ep,'dev',s.toFixed(1),'th',th.map(x=>x.toFixed(2)).join(','));if(s>best.s)best={s,th:th.slice(),ep};}
}
fs.writeFileSync(process.argv[7],JSON.stringify({best,final:th,log,train:TRAIN,lr,EP,KS,algo:'self-critical policy gradient, linear residual over ATC candidates'}));
