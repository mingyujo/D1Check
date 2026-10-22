'use strict';
const {serviceFeatures}=require('./service_features.cjs');let checks=0;
function requireTrue(x){checks++;if(!x)throw Error('Service contract regression');}
const cpu={route:'detection_CPU',phase:'INFER'},gpu={route:'classification_GPU',phase:'POST',phase_progress:0,cpu_service_s:.1},npu={route:'classification_NPU',phase:'POST',phase_progress:0,cpu_service_s:.1};
const a=serviceFeatures([cpu,gpu,npu],gpu);
requireTrue(a.CPU_server===1&&a.CPU_post_service===1&&a.CPU_detection_infer===0);
requireTrue(a.CPU_waiting_owners===2&&a.POST_wall_owners===2);
requireTrue(a.GPU_host_infer_proxy===0&&a.NPU_host_infer_proxy===0);
requireTrue(Object.values(a.held_slots).every(x=>x===1));
const b=serviceFeatures([cpu,gpu,npu],cpu);
requireTrue(b.CPU_detection_infer===1&&b.CPU_post_service===0&&b.CPU_waiting_owners===2);
const c=serviceFeatures([{route:'classification_GPU',phase:'INFER'},{route:'classification_NPU',phase:'INFER'}],null);
requireTrue(c.CPU_server===0&&c.GPU_host_infer_proxy===1&&c.NPU_host_infer_proxy===1);
requireTrue(serviceFeatures([],null).CPU_server===0);
let rejected=false;try{serviceFeatures([cpu,{...cpu}],cpu)}catch{rejected=true}requireTrue(rejected);
rejected=false;try{serviceFeatures([cpu],gpu)}catch{rejected=true}requireTrue(rejected);
rejected=false;try{serviceFeatures([{...gpu,phase_progress:.1}],null)}catch{rejected=true}requireTrue(!rejected);
console.log(JSON.stringify({status:'PASS',checks,scope:'Blocked CPU infer/POST are not counted as active CPU service; held slots preserved; no plant or power fit changed'}));
