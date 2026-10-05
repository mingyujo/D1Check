"""Redraw the published control-only curve from shared CSV; no device/raw dependency."""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',default=str(Path(__file__).with_name('ap_paths.csv')))
    p.add_argument('--output',required=True)
    args=p.parse_args();out=Path(args.output)
    if out.exists():raise FileExistsError('fresh figure output required')
    with Path(args.input).open(encoding='utf-8') as stream:rows=list(csv.DictReader(stream))
    if len(rows)!=56 or {r['role'] for r in rows}!={'development_0_C'}:
        raise ValueError('published completed control only')
    ts=[float(r['common_s']) for r in rows];obs=[float(r['observed_c']) for r in rows];pred=[float(r['m0_c']) for r in rows]
    fig,ax=plt.subplots(2,1,figsize=(10,6),sharex=True,constrained_layout=True)
    ax[0].plot(ts,obs,label='Observed C control',color='black')
    ax[0].plot(ts,pred,label='Unchanged M0; diagnostic');ax[0].legend();ax[0].set_ylabel('AP C')
    ax[1].plot(ts,[v-y for y,v in zip(obs,pred)],label='M0 - observed')
    ax[1].axhline(0,color='gray');ax[1].set_ylabel('Residual C');ax[1].set_xlabel('Seconds since common-window origin')
    for a in ax:a.grid(alpha=.2)
    fig.suptitle('Completed control only; study stopped before load; no new model confirmation')
    out.mkdir(parents=True)
    fig.savefig(out/'control_ap.svg');fig.savefig(out/'control_ap.png',dpi=120);plt.close(fig)
    f=out/'control_ap.svg';f.write_text('\n'.join(line.rstrip() for line in f.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')


if __name__=='__main__':main()
