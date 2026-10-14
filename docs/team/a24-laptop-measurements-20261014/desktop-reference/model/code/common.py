"""Run-local IO and immutable identities. No device, network or old-run writes."""
import hashlib, json, os, gzip, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/ROLLING-ATC-RL-37/V2"
VENDOR = WORK / "vendor"
ALPHAS = (.70, .80, .90, .95, 1.)
SEEDS = (37001, 37003, 37007)
H120 = 120_000_000_000
H180 = 180_000_000_000
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
def save(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    with temp.open("r+b") as f:os.fsync(f.fileno())
    os.replace(temp,path)
def append(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as f:
        f.write(json.dumps(value,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n")
        f.flush();os.fsync(f.fileno())
def gzsave(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    with gzip.open(temp,"wt",encoding="utf-8",compresslevel=3) as f:
        json.dump(value,f,ensure_ascii=False,separators=(",",":"),allow_nan=False)
    with temp.open("r+b") as f:os.fsync(f.fileno())
    os.replace(temp,path)
def stamp():
    return time.time()
