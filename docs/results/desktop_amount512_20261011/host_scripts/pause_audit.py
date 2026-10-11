import hashlib
import json
from pathlib import Path
import shutil
import sys

base=Path(__file__).resolve().parent
root=base/'bundle/D1Check-desktop-cpu-20261011'
dest=root/'output/desktop_joint_amount_amount512_desktop_20261011_a'
sys.path.insert(0,str(root))
from tools import d1_joint_amount_cli as cli
reg=cli.check_task(dest)
clock=cli.x.read(dest/'clock.json')
assert clock['running_since'] is None and clock['consumed_active_seconds']>0
assert not (dest/'owner.lock').exists()
payload=cli.x.r.torch.load(dest/'session_latest.pt',map_location='cpu',weights_only=False)
learners,cursor,consumption=cli.session.restore(payload)
assert cursor==dict(case=8,next_seed=1)
assert consumption==cli.Budget(dest).used()
assert consumption['learning_starts']==25 and consumption['native_starts']==473
states=[]
for seed in (11,23,37):
    assert cli.session.digest(learners[seed].snapshot())==cli.session.digest(payload['learners'][str(seed)])
    states.append(dict(seed=seed,accepted_episodes=learners[seed].accepted_episodes,pending_episodes=len(learners[seed].pending_episodes),updates=learners[seed].update_count,optimizer_steps=learners[seed].optimizer_steps))
assert [q['accepted_episodes'] for q in states]==[73,72,72]
assert [q['pending_episodes'] for q in states]==[1,0,0]
assert cli.session.digest(cli.x.r.training.rng_state())==cli.session.digest(payload['session_rng'])
shutil.copy2(dest/'session_latest.pt',base/'paused_session.pt')
receipt=dict(status='PASS_real_safe_boundary_stop_full3learner_sharedRNG_partial_restore',cursor=cursor,consumption=consumption,clock=clock,states=states,shared_session_sha256=cli.x.sha(dest/'session_latest.pt'),registration_sha256=cli.x.sha(dest/'registration.json'),next_actual_learning_identity='train_23_0008',full_restore_digest_equal=True,force_termination=False,budget_reset=False,clock_reset=False)
(base/'pause_verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
