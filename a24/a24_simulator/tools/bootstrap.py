"""Verify and materialize local package objects. No network or simulation."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'reference/model_integration'))
from runtime_guard import pin,read,relocated
def main():
    rows=read(ROOT/'data/CORE_MANIFEST.json')
    for row in rows:pin({'path':row['original_path'],'sha256':row['sha256'],'bytes':row['bytes']})
    print('PASS: %s exact-byte local inputs; no HTTP, environment, training or scheduler'%len(rows))
if __name__=='__main__':main()
