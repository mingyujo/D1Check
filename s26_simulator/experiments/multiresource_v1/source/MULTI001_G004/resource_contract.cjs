'use strict';
const ROUTES=['classification_CPU','classification_GPU','classification_NPU','detection_CPU'];
const slot=r=>r.endsWith('_GPU')?'GPU':r.endsWith('_NPU')?'NPU':'CPU';
const knownPair=(a,b)=>[a,b].includes('detection_CPU')&&[a,b].some(r=>r==='classification_GPU'||r==='classification_NPU');
const legal=(route,owners,capacity)=>ROUTES.includes(route)&&owners.length<capacity&&!owners.some(o=>slot(o.route)===slot(route));
const allowed=q=>q.task==='detection'?['detection_CPU']:ROUTES.slice(0,3);
const FIFO=(a,b)=>a.arrival-b.arrival||a.ordinal-b.ordinal;
function chooseCPU(owners,current){if(current&&owners.includes(current)&&needsCPU(current))return current;return owners.filter(needsCPU).sort((a,b)=>a.cpu_ticket-b.cpu_ticket||a.ordinal-b.ordinal)[0]??null}
const needsCPU=o=>o.phase==='INFER'&&slot(o.route)==='CPU'||['ADMISSION','POST'].includes(o.phase)&&o.phase_progress<o.cpu_service_s-1e-12;
// These are the frozen fit's observed wall-phase proxies, NOT CPU utilization.
// The shared CPU server controls work progress and is logged independently.
function activity(owners,cpu,model){const a=Array(9).fill(0);for(const o of owners){if(o.phase==='INFER')a[['classification_CPU','detection_CPU','classification_GPU','classification_NPU'].indexOf(o.route)]++;else if(['ADMISSION','POST'].includes(o.phase))a[o.phase==='ADMISSION'?4:5]++;else a[7]++}a[6]=Number(owners.length>0);for(let i=0;i<owners.length;i++)for(let j=i+1;j<owners.length;j++)a[8]+=knownPair(owners[i].route,owners[j].route)?1:model.unknown_pair_weight;return a}
module.exports={ROUTES,slot,knownPair,legal,allowed,FIFO,needsCPU,chooseCPU,activity};
