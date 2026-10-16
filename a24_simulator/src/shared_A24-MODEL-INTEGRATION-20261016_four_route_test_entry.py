import os,runpy,sys
from pathlib import Path
here=Path(__file__).resolve()
os.environ['A24_LAB_GUARD_ENTRY']=str(here)
script='test_four_route.py'
if sys.argv[1:2]==['--preflight']:
    del sys.argv[1];script='preflight_four_route.py'
runpy.run_path(str(here.parent/script),run_name='__main__')
