"""Named entry so existing A24/S26 own-worker guards recognize this producer."""
import os, runpy
from pathlib import Path
os.environ['A24_LAB_GUARD_ENTRY']=str(Path(__file__).resolve())
runpy.run_path(str(Path(__file__).with_name('lab_backend.py')),run_name='__main__')
