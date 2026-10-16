"""Start Node without leaving a waiting Python producer behind."""
from pathlib import Path
import argparse,os,subprocess,sys
P=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8766);a=ap.parse_args()
for script in ('bootstrap.py','configure_v2.py'):subprocess.run([sys.executable,'-B',str(P/'tools'/script)],check=True)
env=dict(os.environ,A24_PYTHON=sys.executable,PORT=str(a.port))
os.execvpe('node',['node',str(P/'src/server_v2.cjs')],env)
