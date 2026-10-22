'use strict';
// New ABI. Never feed these channels into the old wall-phase fitted coefficients.
const routeSlot=r=>r.endsWith('_GPU')?'GPU':r.endsWith('_NPU')?'NPU':'CPU';
function serviceFeatures(owners,cpu){
  const out={CPU_server:0,CPU_classification_infer:0,CPU_detection_infer:0,CPU_admission_service:0,CPU_post_service:0,
    GPU_host_infer_proxy:0,NPU_host_infer_proxy:0,CPU_waiting_owners:0,POST_wall_owners:0,
    held_slots:{CPU:0,GPU:0,NPU:0},resident_power_identified:false,hardware_core_utilization_identified:false};
  const slots=new Set;
  for(const o of owners){
    const s=routeSlot(o.route);if(slots.has(s))throw Error('Duplicate reserved slot');slots.add(s);out.held_slots[s]=1;
    if(o.phase==='POST')out.POST_wall_owners++;
    const cpuInfer=o.phase==='INFER'&&s==='CPU';
    const cpuPrefix=['ADMISSION','POST'].includes(o.phase)&&o.phase_progress<o.cpu_service_s-1e-12;
    if((cpuInfer||cpuPrefix)&&cpu!==o)out.CPU_waiting_owners++;
    if(o.phase==='INFER'&&s!=='CPU')out[s+'_host_infer_proxy']=1;
  }
  if(cpu){
    if(!owners.includes(cpu))throw Error('CPU grant does not belong to live owner');
    out.CPU_server=1;
    if(cpu.phase==='INFER'&&routeSlot(cpu.route)==='CPU')out[cpu.route==='classification_CPU'?'CPU_classification_infer':'CPU_detection_infer']=1;
    else if(['ADMISSION','POST'].includes(cpu.phase)&&cpu.phase_progress<cpu.cpu_service_s-1e-12)out[cpu.phase==='POST'?'CPU_post_service':'CPU_admission_service']=1;
    else throw Error('CPU grant is stale or not a CPU service phase');
  }
  if(out.CPU_classification_infer+out.CPU_detection_infer+out.CPU_admission_service+out.CPU_post_service!==out.CPU_server)throw Error('CPU service conservation');
  return out;
}
module.exports={serviceFeatures};
