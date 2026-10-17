import time, json, rl_lab as R
e = R.Engine(); lr = R.learn.Learner(1, 'JOINT_ATC_RL')
for load in [{"kind":"R21","slot":"R1-4-M128_BASE"},{"kind":"GEN","slot":"R1-4-M128_BASE","dur":25,"gap":0.537,"mixC":5,"mixD":3,"shape":"smooth"}]:
    for collect in (False, True):
        ctl = lr.controller(.95, .5, collect=collect); t = time.time(); s = e.rl(ctl, load, 1000)
        print(collect, round(time.time()-t,2), {k: s[k] for k in ('planned','on_time','N_on','unfinished','J','AP_mean','heat_area','routes','rl_stats')})
# determinism: argmax twice same
a = e.rl(lr.controller(.95,.5,False), {"kind":"R21","slot":"R1-6-SMOOTH128_BASE"}, 7); b = e.rl(lr.controller(.95,.5,False), {"kind":"R21","slot":"R1-6-SMOOTH128_BASE"}, 7)
print('deterministic', a['J']==b['J'] and a['on_time']==b['on_time'])
e.close()
