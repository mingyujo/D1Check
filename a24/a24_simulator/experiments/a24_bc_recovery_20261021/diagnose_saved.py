"""Post-run TRAIN diagnostics only; no fitting, environment or model selection."""
from study import *

def acc(net,frames):
    good=0
    for start in range(0,len(frames),128):
        part=frames[start:start+128]
        with torch.no_grad():pred=net(torch.from_numpy(np.stack([f['x'] for f in part])),torch.from_numpy(np.stack([f['mask'] for f in part])))[0].argmax(-1).numpy()
        good+=sum(bool(f['teacher_mask'][pred[i]]) for i,f in enumerate(part))
    return dict(correct=good,n=len(frames),accuracy=good/len(frames))

def main():
    frames=loadpt(O/'TRAIN_FRAMES.pt.gz')['frames'];original=loadpt(R/read(PACK/'DATASET.json')['dataset']['path'])['frames'];guarded=loadpt(O/'ORIGINAL_RELABELLED.pt.gz')['frames']
    oldnet=Learner(state=loadpt(CHECKPOINT)).net;newnet=Learner(state=loadpt(O/'BC.RECOVERED.pt.gz')).net
    def expand(v):return v if abs(v)<=5 else math.copysign(5+math.expm1(abs(v)-5),v)
    def coverage(rows):return dict(frames=len(rows),min_temperature_C=min(26+10*expand(float(f['x'][0,18])) for f in rows),max_temperature_C=max(26+10*expand(float(f['x'][0,18])) for f in rows),max_queue=max(round(32*expand(float(f['x'][0,13]))) for f in rows))
    by_source={case:coverage([f for f in frames if f['source_case']==case]) for case in sorted({f['source_case'] for f in frames})}
    datasets={name:{'old':acc(oldnet,rows),'recovered':acc(newnet,rows)} for name,rows in [('original_unfiltered',original),('original_guarded',guarded),('augmented_selected',frames)]}
    trace=read(O/'BC_TRAINING.json');assert abs(datasets['augmented_selected']['old']['accuracy']-trace['initial_compatible_accuracy'])<1e-7 and abs(datasets['augmented_selected']['recovered']['accuracy']-trace['logs'][-1]['compatible_accuracy'])<1e-7
    data=dict(status='PASS',datasets=datasets,selected_TRAIN_coverage=coverage(frames),by_source=by_source,source='Actual selected TRAIN tensors, with temperature/queue decoded from declared original50 features',scope='TRAIN diagnostics; not heldout generalization or EVAL outcome',new_environment=0,new_fit=0)
    new(O/'TRAIN_DIAGNOSTICS.json',data);print(json.dumps(data,ensure_ascii=False))

if __name__=='__main__':main()
