import sys
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'a24_s26_scale_20261022'))
from scale_common import *
H=Path(__file__).resolve().parent;O=A/'results/A24_S26_MATCHED_BC_20261022_01';V=A/'reviews/A24_S26_MATCHED_BC_20261022_01'
MODES=['FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_OLD','BC_OLD','TEACHER_MATCH','TEACHER_GUARD','BC_GUARD_FROZEN','BC_MATCHED']
loadpt,equal=legacy.loadpt,legacy.equal
def pt(path,value):
    import io,torch
    buf=io.BytesIO();torch.save(value,buf)
    with Path(path).open('xb') as f:f.write(gzip.compress(buf.getvalue(),mtime=0))
OLD_RISK=A/'results/A24_NN_URGENT_TIE_20261021_01/RISK_CALIBRATION.json'
TRAIN_MAX_FRAMES=768
