from pathlib import Path
import sys,json,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'reference/model_integration'))
from runtime_guard import process_guard
try:
    p=process_guard(ROOT/'tools/guard.py')
    free=shutil.disk_usage(ROOT.anchor).free
    print(json.dumps({'ok':free>=8*1024**3,'free':free,'process':p}))
except Exception as e:print(json.dumps({'ok':False,'reason':str(e)}))
