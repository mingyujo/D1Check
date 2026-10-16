"""Clean-folder verification: all pinned inputs must resolve inside this copy."""
from pathlib import Path
import sys,json
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'tools'))
import bootstrap,configure_v2
bootstrap.main();configure_v2.main()
sys.path.insert(0,str(P/'src'))
import lab_backend as L
reg=L.read(P/'runtime/registration.json')
count=0
for spec in [*reg['source_pins'],*reg['input_pins']]:
    actual=L.pin(spec)
    if not actual.resolve().is_relative_to(P.resolve()):raise RuntimeError('Input escaped standalone folder: '+str(actual))
    count+=1
model,thermal,profile=L.initialize(reg)
catalog=L.read(L.pin(reg['catalog_pin']));v=L.validate_input({'requests':[{'profile':'C_M128','priority':'U','arrival_s':35,'deadline_s':36.54},{'profile':'D_M128','priority':'N','arrival_s':35,'deadline_s':40}],'rl_seed':20261028},catalog['profiles'])
public,contexts=L.prepare_public(v,catalog['templates'],catalog['profiles']);m=L.Model(model,contexts)
actor=L.RLPolicy(m,public,thermal,profile,L.pin(reg['checkpoints']['20261028']),.95,True)
assert m.metadata['model_digest']==reg['expected_four_route_timing_digest']
assert thermal['model_sha256']==reg['expected_four_route_AP_sha256']
result={'status':'PASS_STANDALONE_FOLDER_NO_ORIGINAL_INPUT_ACCESS','pins_resolved_inside_copy':count,'model_digest':m.metadata['model_digest'],'network_sha256':actor.network_sha,'new_environment_START':0,'NN_training':0}
(P/'results/CLEANROOM_RUNTIME.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
