"""Guarded postrun AST/Node syntax checks. No simulator or numerical cost import."""
import ast,importlib.util,json,msvcrt,subprocess,sys,traceback
from pathlib import Path
op_path=Path(sys.argv[1]);op=json.loads(op_path.read_text(encoding='utf-8-sig'));s=importlib.util.spec_from_file_location('frozen_owner',op['owner_source']);owner=importlib.util.module_from_spec(s);s.loader.exec_module(owner);owner.verify(op);census=owner.Census();handle=None;locked=False;out=Path(op['output_dir'])
try:
 own=census.get();handle=Path(op['shared_byte_mutex']['path']).open('r+b');handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);locked=True;out.mkdir();owner.save(out/'OWNER.json',own['self']);assert owner.read(Path(op['production_dir'])/'AUDIT_V1/FINAL_AUDIT.json')['status']=='PASS';sources=Path(op['postrun_dir']);py=[];js=[]
 for f in sources.glob('*.py'):ast.parse(f.read_text(encoding='utf-8-sig'),filename=str(f));py.append(dict(path=str(f),sha256=owner.sha(f)))
 for f in sources.glob('*.cjs'):
  census.get();subprocess.run([op['node_path'],'--check',str(f)],check=True,creationflags=subprocess.CREATE_NO_WINDOW);js.append(dict(path=str(f),sha256=owner.sha(f)))
 html=(sources/'multi_view.template.html').read_text(encoding='utf-8');assert html.count('__GZIP_BASE64__')==1;assert html.count('<script>')==1;inline=html.split('<script>')[1].split('</script>')[0];f=out/'inline_view.cjs';f.write_text(inline,encoding='utf-8');subprocess.run([op['node_path'],'--check',str(f)],check=True,creationflags=subprocess.CREATE_NO_WINDOW);js.append(dict(path=str(f),sha256=owner.sha(f)));owner.verify(op);owner.save(out/'RESULT.json',dict(status='PASS',python_AST=py,Node_syntax=js,browser_executed=False,new_policy_environments=0,new_cost_replay=0,new_fit=0,new_RL=0))
except BaseException:
 if out.exists():owner.save(out/'FAILURE.json',dict(status='FAILED_PRESERVED',traceback=traceback.format_exc()))
 raise
finally:
 if handle:
  if locked:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
  handle.close()
 census.close()
