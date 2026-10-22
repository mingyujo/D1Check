"""Saved-only independent Float64 NN argmax check; no environment execution."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import hashlib
import json
from pathlib import Path
import numpy as np
from study import H, O, R, read, loadpt, stamp


def main():
    op = read(H / 'OPERATION.json')
    snap = loadpt(R / read(O / 'RESULT.json')['checkpoint']['path'])
    net = {k:v.detach().numpy().astype(np.float64) for k,v in snap['network'].items()}
    def linear(x, n):
        return x @ net[n+'.weight'].T + net[n+'.bias']
    count, maxregret, ties = 0, 0., 0
    for row in read(O / 'RESULT.json')['rows']:
        if row['status'] == 'FAIL' or row['policy'] != 'IDLE_BC':
            continue
        assert row['network_sha256'] == snap['network_sha256']
        calls = read(R / row['raw']['path'])['calls']
        for start in range(0, len(calls), 128):
            cs = calls[start:start+128]
            x = np.asarray([q['x'] for q in cs], np.float64)
            mask = np.asarray([q['mask'] for q in cs], bool)
            e = np.tanh(linear(x, 'encode.0'))
            mean = (e*mask[:,:,None]).sum(1)/mask.sum(1)[:,None]
            maximum = np.where(mask[:,:,None], e, -1e9).max(1)
            ctx = np.concatenate([mean, maximum], -1)
            logits = linear(np.tanh(linear(np.concatenate([e, np.broadcast_to(ctx[:,None,:], (len(cs),36,96))], -1), 'actor.0')), 'actor.2').squeeze(-1)
            logits = np.where(mask, logits, -1e9)
            for i, q in enumerate(cs):
                assert mask[i,q['chosen']] and q['actions'][q['chosen']] == q['action']
                regret = float(logits[i].max()-logits[i,q['chosen']])
                maxregret = max(maxregret, regret)
                assert regret < 2e-6
                ties += int(int(logits[i].argmax()) != q['chosen'])
                count += 1
    with (O / 'NN_AUDIT.json').open('x', encoding='utf-8') as f:
        json.dump(dict(status='PASS', utc=stamp(), frames=count, max_Float64_argmax_regret=maxregret,
                       rounding_ties=ties, new_environment=0,
                       source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()), f, indent=2)
    print('QUEUE_PRESSURE_FLOAT64_NN_PASS', count, maxregret)


if __name__ == '__main__':
    main()
