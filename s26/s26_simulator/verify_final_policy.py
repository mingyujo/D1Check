"""Read-only verification of the adopted frozen research policy; no forward/simulation/training."""
import hashlib,json
from pathlib import Path
S=Path(__file__).resolve().parent;R=S.parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 c=read(S/'FINAL_POLICY.json');checks=0
 def need(ok,msg):
  nonlocal checks
  checks+=1
  if not ok:raise AssertionError(msg)
 need(c['representative']['seed']==881087 and not c['representative']['ensemble'],'Original representative, single model')
 need(c['methodology']['teacher_learning'] and c['methodology']['PPO'],'Declared teacher+PPO methodology')
 need(not c['methodology']['deadline_protection'] and not c['methodology']['post_neural_override'],'No deadline shield or post-NN override')
 need(not c['methodology']['PPO_incremental_benefit_demonstrated'] and not c['claims']['PPO_additional_benefit'],'No unsupported PPO-only claim')
 need(c['claims']['physical_accuracy_gate']=='FAIL' and not c['claims']['real_device_savings_certified'],'Physical model limitation retained')
 need(c['runtime']['neural']['evaluated_inference_selection'].startswith('argmax'),'Retain original evaluated inference')
 snap=R/c['integrity']['published_snapshot_manifest'];need(sha(snap)==c['integrity']['snapshot_manifest_sha256'],'Published snapshot manifest')
 published={x['path']:x for x in read(snap)['files']}
 for pin in c['integrity']['source_pins']:
  p=(R/pin['path']).resolve();need(p.is_relative_to(R.resolve()) and p.is_file(),'Bound local path');need(sha(p)==pin['sha256'] and p.stat().st_size==pin['bytes'],'Frozen bound source SHA');need(published[pin['path']]['sha256']==pin['sha256'],'Same published scientific bytes')
 cp=c['representative']['checkpoint'];need(sha(S/cp['path'])==cp['file_sha256'],'Final checkpoint SHA');need(sha(S/c['teacher_control']['path'])==c['teacher_control']['file_sha256'],'BC control preserved')
 sel=read(R/c['representative']['selection_record']);need(sel['selected']==881087 and sha(R/c['representative']['selection_record'])==c['representative']['selection_sha256'],'Original pre-EVAL DEV selection')
 evidence=read(R/c['primary_evidence']['source']);gg={x['method']:x for x in evidence['groups'] if x['load']==.85}
 for label,key in [('baseline','EDF_GPU_FIRST'),('representative','DEV_SELECTED_EVENT_PPO'),('three_seed_aggregate','EVENT_PPO'),('BC_control','BC_FROZEN')]:need(gg[key]==c['primary_evidence'][label],'Correct old cohort / aggregation '+label)
 need(gg['DEV_SELECTED_EVENT_PPO']['on_percent']==97.0703125 and gg['EVENT_PPO']['rows']==12,'Representative and 3seed aggregate distinguished')
 need(c['runtime']['saved_balance']==read(S/'final_policy_20261019/CHECKPOINT_INSPECTION.json')['items']['selected']['balance'],'Saved final balance, no inferred replacement')
 for rel in c['preservation']['secondary_reports']:need((R/rel).exists(),'Secondary result preserved')
 for rel in ['s26_simulator/START_HERE.md','s26_simulator/STATUS.md','s26_simulator/HANDOFF.md','s26_simulator/docs/NEXT_STEPS.md','s26_simulator/AGENTS.md','docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md']:need((R/rel).read_text(encoding='utf-8-sig').startswith('<!-- S26_FINAL_POLICY_ADOPTED_BEGIN -->'),'Current entry points to adopted policy')
 need(all(v==0 for k,v in c['scope'].items() if k.startswith('new_')),'No new scientific work/budget')
 print(json.dumps(dict(status='PASS_ADOPTED_FROZEN_POLICY_BINDING',checks=checks,seed=881087,source_pins=len(c['integrity']['source_pins']),checkpoint_sha256=cp['file_sha256'],new_forward_calls=0,new_environment=0,new_training=0,new_measurements=0,new_fits=0),ensure_ascii=False))
if __name__=='__main__':main()
