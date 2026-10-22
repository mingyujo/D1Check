"""Independent Float64 argmax audit under the new eligibility masks."""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import datetime
import hashlib
from pathlib import Path
import numpy as np
from review_saved import O, P, R, read, save
from common_transfer import loadpt


def main():
    checkpoint = loadpt(P / 'BC.FINAL.pt.gz')
    weights = {k:v.detach().numpy().astype(np.float64) for k, v in checkpoint['network'].items()}
    def linear(x, name):
        return x @ weights[name+'.weight'].T + weights[name+'.bias']
    replays = {(r['case'], r['decision_index']):r for r in read(O / 'DECISION_REPLAY.json.gz')}
    count, maxregret, ties = 0, 0., 0
    for row in read(P / 'RESULT.json')['rows']:
        calls = read(R / row['raw']['path'])['calls']
        for start in range(0, len(calls), 128):
            cs = calls[start:start+128]
            rr = [replays[row['case'], i] for i in range(start, start+len(cs))]
            x = np.asarray([c['x'] for c in cs], np.float64)
            mask = np.asarray([r['mask'] for r in rr], bool)
            e = np.tanh(linear(x, 'encode.0'))
            mean = (e*mask[:,:,None]).sum(1) / mask.sum(1)[:,None]
            maximum = np.where(mask[:,:,None], e, -1e9).max(1)
            ctx = np.concatenate([mean, maximum], -1)
            actor_input = np.concatenate([e, np.broadcast_to(ctx[:,None,:], (len(cs), 36, 96))], -1)
            logits = linear(np.tanh(linear(actor_input, 'actor.0')), 'actor.2').squeeze(-1)
            logits = np.where(mask, logits, -1e9)
            for i, r in enumerate(rr):
                selected = r['new_chosen']
                assert mask[i, selected]
                regret = float(logits[i].max() - logits[i, selected])
                assert regret < 2e-6
                maxregret = max(maxregret, regret)
                ties += int(int(logits[i].argmax()) != selected)
                count += 1
    assert count == 3781
    save('NN_AUDIT.json', dict(status='PASS', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        frames=count, max_Float64_argmax_regret=maxregret, rounding_ties=ties,
        new_environment=0, new_fit=0,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    print('IDLE_WAIT_FLOAT64_NN_PASS', count, maxregret)


if __name__ == '__main__':
    main()
