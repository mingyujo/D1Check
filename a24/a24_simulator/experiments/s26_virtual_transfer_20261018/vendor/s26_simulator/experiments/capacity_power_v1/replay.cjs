'use strict';
const fs=require('node:fs');
function steps(intervals,start=-30){
 const events=new Map([[start,Array(8).fill(0)]]);
 for(let j=0;j<8;j++)for(let [a,b,w] of intervals[j]){a=Math.max(a,start);if(b<=a)continue;for(const [t,delta] of [[a,w],[b,-w]]){if(!events.has(t))events.set(t,Array(8).fill(0));events.get(t)[j]+=delta;}}
 let current=Array(8).fill(0),prior=null;const out=[];
 for(const [t,d] of [...events].sort((a,b)=>a[0]-b[0])){current=current.map((x,j)=>x+d[j]);if(current.some(x=>x< -1e-7))throw Error('Negative source activity');
  const f=[[0,1,4,5].some(j=>current[j]>1e-9),current[1]>1e-9,current[2]>1e-9,current[3]>1e-9,current.some(x=>x>1e-9)].map(Number);
  if(prior===null||f.some((x,j)=>x!==prior[j])){out.push([t,f]);prior=f;}}
 return out;
}
function features(step,times,baseline,start=-30){
 const changes=new Map(step),grid=[...new Set([start,...step.map(x=>x[0]).filter(t=>t<=times.at(-1)),...times,...times.map(t=>t-.5)])].sort((a,b)=>a-b);
 let v=Array(5).fill(0),area=Array(5).fill(0),z=Array.from({length:3},()=>Array(5).fill(0)),previous=start;
 const areas=new Map,states=new Map;
 for(const t of grid){const dt=t-previous;area=area.map((x,j)=>x+dt*v[j]);z=z.map((xs,k)=>xs.map((x,j)=>Math.exp(-dt/[1,10,60][k])*x+-Math.expm1(-dt/[1,10,60][k])*v[j]));
  areas.set(t,area.slice());states.set(t,z.map(xs=>xs.slice()));if(changes.has(t))v=changes.get(t);previous=t;}
 return times.map(t=>[1,baseline,...areas.get(t).map((x,j)=>(x-areas.get(t-.5)[j])/.5),...states.get(t).flat()]);
}
function predict(X,m){return X.map(row=>row.reduce((sum,v,j)=>sum+v/m.scale[j]*m.coef[j],0));}
module.exports={steps,features,predict};
if(require.main===module){
 if(process.argv[2]==='test'){
  const activity=Array.from({length:9},()=>[]);activity[5]=[[0,10,3]];activity[6]=[[0,10,3]];
  const s=steps(activity),x=features(s,[.25,1,20],.6);if(x[0][2]!==.5||x[0][6]!==.5||Math.abs(x[0][7]+Math.expm1(-.25))>1e-12||x.some(r=>r.slice(2).some(v=>v>1+1e-9)))throw Error('Capacity/pulse regression');
  console.log(JSON.stringify({status:'PASS',checks:4,scope:'Three POST wall owners map to one CPU/owner demand; analytic pulse box/tail bounds'}));
 }else{const input=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(input.cases.map(e=>{const x=features(steps(e.intervals),e.times,e.baseline);return {id:e.id,predicted:predict(x,input.models[e.model]),max_proxy:Math.max(...x.flatMap(r=>r.slice(2)))};})));}
}
