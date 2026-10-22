"""Create a separate independent JS checker; prior checker stays sealed."""
from pathlib import Path
H=Path(__file__).resolve().parent;s=(H.parent/'a24_fair_nn_bc_20261021/audit.cjs').read_text(encoding='utf8')
s=s.replace('A24_FAIR_NN_BC_20261021_01','A24_NN_MARGIN_EXACT_20261021_01')
s=s.replace('all.length===32','all.length===36').replace('All eight policies / four cases','All nine policies / four cases')
s=s.replace("'COST_IMITATION','BC_NEURAL_FAIR']","'COST_IMITATION','BC_NEURAL_PREVIOUS','BC_NEURAL_REPAIRED']")
needle=" ok(c.teacher_index===teacherIndex,'Independent fair teacher target');"
assert needle in s
addition="""
 const values=usable.map(i=>teacher[i]),mean=values.reduce((a,b)=>a+b,0)/values.length,scale=Math.max(1e-6,Math.sqrt(values.reduce((a,b)=>a+(b-mean)**2,0)/values.length));
 const compress=v=>Math.abs(v)<=5?v:Math.sign(v)*(5+Math.log1p(Math.abs(v)-5));
 for(let i=0;i<36;i++){
  const v=c.relative_cost_input?(mask[i]?compress((teacher[i]-mean)/scale):0):(i<c.actions.length?compress(teacher[i]/10):0);
  near(c.x[i][28],Math.fround(v),'Independent candidate cost normalization input',2e-6);
 }
"""
s=s.replace(needle,needle+addition)
s=s.replace(" ok(JSON.stringify(c.teacher_mask)===JSON.stringify(mask.map((v,i)=>v&&teacher[i]<=bestScore+1e-8)),'Exact cost-compatible action labels');", " ok(JSON.stringify(c.cost_compatible_mask)===JSON.stringify(mask.map((v,i)=>v&&teacher[i]<=bestScore+1e-8)),'Separate compatible-cost diagnostic');\n ok(JSON.stringify(c.teacher_mask)===JSON.stringify(mask.map((v,i)=>i===teacherIndex)),'Single exact teacher action label, including ties');")
with (H/'audit.cjs').open('x',encoding='utf8',newline='\n') as f:f.write(s)
print('PREPARED_SAVED_AUDITOR')
