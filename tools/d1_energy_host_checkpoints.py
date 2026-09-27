"""Durable, bounded host checkpoints for future energy collection runs.

They describe host progress, never completion or confirmed device consumption.
Abrupt process termination can leave the last checkpoint without a final receipt.
"""

import datetime
import json
import os
from pathlib import Path
import time
import uuid


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic_new(path, value):
    """Create one JSON file by fsync + same-directory rename; never reuse a name."""
    path=Path(path)
    if path.exists():
        raise FileExistsError(path)
    temporary=path.with_name(path.name+'.partial-'+uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            stream.write((json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8'))
            stream.flush();os.fsync(stream.fileno())
        if path.exists():
            raise FileExistsError(path)
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()


class Checkpoints:
    def __init__(self,root,plan_sha256):
        self.root=Path(root);self.root.mkdir(exist_ok=False)
        self.plan_sha256=plan_sha256;self.sequence=0

    def mark(self,stage,**details):
        record=dict(sequence=self.sequence,stage=stage,utc=utc(),monotonic=time.monotonic(),
                    host_pid=os.getpid(),host_parent_pid=os.getppid(),
                    plan_sha256=self.plan_sha256,**details)
        atomic_new(self.root/f'{self.sequence:04d}.json',record)
        self.sequence+=1
        return record
