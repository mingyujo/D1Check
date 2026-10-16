"""Portable explicit entrypoint. No scheduled or import-triggered work."""
from pathlib import Path
import argparse,os,subprocess,sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['verify','serve']);ap.add_argument('--port',default=8766,type=int);a=ap.parse_args()
    subprocess.run([sys.executable,'-B',str(ROOT/'tools/bootstrap.py')],check=True)
    if a.command=='serve':
        subprocess.run([sys.executable,'-B',str(ROOT/'tools/configure.py')],check=True)
        env=dict(os.environ,A24_PYTHON=sys.executable,PORT=str(a.port))
        subprocess.run(['node',str(ROOT/'src/server.cjs')],check=True,env=env)
if __name__=='__main__':main()
