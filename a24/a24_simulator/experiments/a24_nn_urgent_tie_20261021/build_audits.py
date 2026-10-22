"""Create saved-only checkers from the preserved independent physics checker."""
from pathlib import Path
H=Path(__file__).resolve().parent
s=(H.parent/'a24_nn_margin_exact_20261021/audit.cjs').read_text(encoding='utf8')
def replace(old,new):
    global s
    assert old in s,old;s=s.replace(old,new)
replace('A24_NN_MARGIN_EXACT_20261021_01','A24_NN_URGENT_TIE_20261021_01')
replace("let checks=0,maxerr=0", "const riskModel=read(path.join(O,'RISK_CALIBRATION.json'));\nlet checks=0,maxerr=0")
replace('const mask=idle.map','let mask=idle.map')
replace('const forced=critical.filter','let forced=critical.filter')
needle=" ok(JSON.stringify(mask)===JSON.stringify(c.mask),'Shared service and normal latest-start mask');"
replacement=""" ok(JSON.stringify(mask)===JSON.stringify(c.previous_service_mask),'Unchanged original nominal service mask');
 const riskPairs=c.forecasts.map((f,j)=>{let risky=0;const visible=new Set(f.visible_ids);for(const q of pending){if(q.priority!=='U'||!visible.has(q.request_id))continue;const got=Object.prototype.hasOwnProperty.call(f.responses_s,q.request_id),end=got?f.responses_s[q.request_id]:f.H_s;risky+=Number(!got||end+riskModel.task_margin_s[q.task]>q.deadline_ns/1e9+1e-8);}return [risky,...pairs[j]];});
 const riskBest=allowed.map(i=>riskPairs[i]).sort((a,b)=>a[0]-b[0]||a[1]-b[1]||a[2]-b[2])[0];
 mask=idle.map((v,i)=>!!v&&i<riskPairs.length&&riskPairs[i].every((v,j)=>v===riskBest[j]));forced=critical.filter(i=>mask[i]);if(forced.length){mask.fill(false);forced.forEach(i=>mask[i]=true);}
 ok(JSON.stringify(riskPairs)===JSON.stringify(c.risk_pairs),'Independent buffered urgent late counts');
 ok(JSON.stringify(riskBest)===JSON.stringify(c.risk_guard.best),'Independent risk optimum');
 for(const task of ['C','D'])near(c.risk_guard.task_margin_s[task],riskModel.task_margin_s[task],'Fixed TRAIN margin',1e-12);
 ok(JSON.stringify(mask)===JSON.stringify(c.mask),'Buffered urgent service and normal latest-start mask');"""
replace(needle,replacement)
replace("near(c.x[i][28],Math.fround(v),'Independent candidate cost normalization input',2e-6);", "near(c.x[i][28],Math.fround(v),'Independent candidate cost normalization input',2e-6);\n  near(c.x[i][49],i<c.actions.length?Math.fround(i/35):0,'Independent public action position',1e-9);")
replace("ok(c.teacher_index===teacherIndex,'Independent fair teacher target');", "ok(c.teacher_index===teacherIndex,'Independent risk teacher target');\n if(policy==='TEACHER_RISK')ok(c.chosen===teacherIndex,'Actual risk teacher choice');")
replace("starts.length<=12", "starts.length<=17")
replace("'12 unit START census'", "'17 unit START census'")
replace("all.length===36,'All nine policies / four cases'", "all.length===44,'All eleven policies / four cases'")
replace("'BC_NEURAL_PREVIOUS','BC_NEURAL_REPAIRED'", "'BC_NEURAL_PREVIOUS','BC_NEURAL_MARGIN','TEACHER_RISK','BC_NEURAL_URGENT'")
replace("['TEACHER_FAIR','COST_IMITATION','BC_NEURAL_PREVIOUS','BC_NEURAL_REPAIRED']", "['TEACHER_FAIR','BC_NEURAL_PREVIOUS','BC_NEURAL_MARGIN','TEACHER_RISK','BC_NEURAL_URGENT']") if "['TEACHER_FAIR','COST_IMITATION','BC_NEURAL_PREVIOUS','BC_NEURAL_REPAIRED']" in s else None
# The preceding policy suffix replacement also updates the delta policy list.
with (H/'audit.cjs').open('x',encoding='utf8',newline='\n') as f:f.write(s)
print('BUILT_SAVED_CHECKER',H/'audit.cjs')
