"""Derive a new saved JS checker without editing the preserved prior checker."""
from pathlib import Path
H=Path(__file__).resolve().parent
s=(H.parent/'a24_service_bc_repair_20261021/audit.cjs').read_text(encoding='utf8')
s=s.replace('A24_SERVICE_BC_REPAIR_20261021_01','A24_FAIR_NN_BC_20261021_01')
start=s.index(" const usable=c.actions.map");end=s.index('\n}',start)
s=s[:start]+''' const usable=c.actions.map((_,i)=>i).filter(i=>mask[i]),bestScore=Math.min(...usable.map(i=>teacher[i])),teacherIndex=usable.find(i=>teacher[i]<=bestScore+1e-8);
 ok(c.teacher_index===teacherIndex,'Independent fair teacher target');
 ok(JSON.stringify(c.teacher_mask)===JSON.stringify(mask.map((v,i)=>v&&teacher[i]<=bestScore+1e-8)),'Exact cost-compatible action labels');
 ok(mask[c.chosen]&&JSON.stringify(c.action)===JSON.stringify(c.actions[c.chosen]),'Neural action eligibility and binding');
 ok(c.post_NN_override===false&&c.future_information===false,'No teacher override');
 regressionChoices++;
'''+s[end:]
s=s.replace('starts.length<=15','starts.length<=12').replace('15 unit START census','12 unit START census')
s=s.replace('all.length===28','all.length===32').replace('All seven policies / four cases','All eight policies / four cases')
s=s.replace("'TEACHER_FAIR','BC_FAIR']","'TEACHER_FAIR','COST_IMITATION','BC_NEURAL_FAIR']")
s=s.replace("['TEACHER_FAIR','BC_FAIR'].includes(x.policy)","['BC_NEURAL_FAIR'].includes(x.policy)")
s=s.replace('learned_regression_choices:regressionChoices','neural_saved_choices:regressionChoices')
assert 'BC_NEURAL_FAIR' in s and 'Exact cost-compatible action labels' in s
with (H/'audit.cjs').open('x',encoding='utf8',newline='\n') as f:f.write(s)
print('PREPARED_INDEPENDENT_SAVED_AUDITOR')
