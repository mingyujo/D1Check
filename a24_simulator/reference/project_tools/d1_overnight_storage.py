"""Lossless NTFS compression of completed workspace artifacts, never deletion.

Per-file absolute path bounds and before/after SHA checks. Excludes live night
tasks, source, user documents, reparse points and other worktrees. Stops once
6GiB is free or after20 minutes. No raw/checkpoint content or names are changed.
"""
import ctypes,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'output/overnight_storage_20261011_v1'
EXTENSIONS={'.pt','.jsonl','.json','.csv','.apk','.so','.log','.txt','.bin'}
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def allocated(path):
    hi=ctypes.c_ulong(0);fn=ctypes.windll.kernel32.GetCompressedFileSizeW;fn.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)];fn.restype=ctypes.c_ulong
    low=fn(str(path),ctypes.byref(hi))
    if low==0xffffffff and ctypes.GetLastError():return None
    return (hi.value<<32)|low
def run():
    LOCAL.mkdir(exist_ok=False);begin=time.time();initial=shutil.disk_usage(ROOT).free;candidates=[]
    for folder in (ROOT/'output').iterdir():
        if not folder.is_dir() or folder.name.startswith('overnight') or (folder/'owner.lock').exists():continue
        if not folder.resolve().is_relative_to(ROOT):continue
        for base,dirs,files in os.walk(folder,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink() and (Path(base)/d).resolve().is_relative_to(ROOT)]
            for name in files:
                path=Path(base)/name
                if path.suffix.lower() not in EXTENSIONS:continue
                try:st=path.stat()
                except OSError:continue
                if st.st_size<256*1024 or getattr(st,'st_file_attributes',0)&(0x400|0x800):continue
                if path.resolve().is_relative_to(ROOT):candidates.append((st.st_size,path))
    candidates.sort(reverse=True,key=lambda v:v[0]);completed=0;saved=0;errors=[]
    with (LOCAL/'files.jsonl').open('a',encoding='utf-8',newline='\n') as journal:
        for size,path in candidates:
            if time.time()-begin>1200 or shutil.disk_usage(ROOT).free>=6*1024**3:break
            absolute=path.resolve()
            if not absolute.is_relative_to(ROOT) or not absolute.is_relative_to(ROOT/'output'):raise ValueError('outside workspace output')
            before=sha(absolute);physical=allocated(absolute)
            call=subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/compact.exe'),'/C','/I','/Q',str(absolute)],capture_output=True,timeout=45)
            after=sha(absolute)
            if before!=after:raise ValueError('content changed by compression: '+str(path.relative_to(ROOT)))
            final=allocated(absolute);gain=max(0,physical-final) if physical is not None and final is not None else 0
            journal.write(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=before,logical_bytes=size,before_allocated=physical,after_allocated=final,saved=gain,exit_code=call.returncode),allow_nan=False)+'\n');journal.flush();os.fsync(journal.fileno())
            completed+=1;saved+=gain
            if call.returncode:errors.append(dict(path=path.relative_to(ROOT).as_posix(),exit_code=call.returncode))
            if completed%20==0:print(json.dumps(dict(compressed_files=completed,saved_MiB=saved/1024**2,free_GiB=shutil.disk_usage(ROOT).free/1024**3)),flush=True)
    result=dict(status='PASS_lossless_compression',files=completed,saved_bytes=saved,initial_free=initial,final_free=shutil.disk_usage(ROOT).free,content_SHA_equal=True,deleted_files=0,moved_files=0,live_task_files_changed=0,errors=errors,seconds=time.time()-begin)
    (LOCAL/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result),flush=True)
if __name__=='__main__':run()
