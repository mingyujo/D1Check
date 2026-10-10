"""d1sim.model_error_v1 — S26 throttle-model error check on energy C (prereg d1sim/docs/모형오차_사전등록_v1.md, commit 9e29851).

predict_energyc.py  frozen models (v2.2 e52a922 main · v2.1 c6a7da2 · v2 θ0.3/θ0.75 42338e7) replay the two energy-C chains
                    through d1sim.v3.predict_v3 (imported, unmodified) — written and committed BEFORE any prediction run.
measure_energyc.py  measured m1~m4 inputs + noise baseline from the 16 valid energy-C cells (judge JSON · raw HAL).
judge_modelerr.py   m1~m5 per cell / block · block pass · k · 3-way verdict (prereg §4) · --selftest.
No file under d1sim/ outside this folder is modified.
"""
