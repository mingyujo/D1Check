"""Prepare four bounded telemetry-only smoke manifests on the host. Never calls ADB."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import uuid
import zipfile

from tools import d1_telemetry_v4 as v
from tools.d1_model_probe import validate_manifest_data


def prepare(final_root,output,apk,seed=20260921):
    final_root=Path(final_root);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    previous=v.read(final_root/'installed.json'); apk_sha=v.digest(Path(apk))
    templates={}
    for phase in 'ABC':
        for path in sorted((final_root/phase/'profiles').glob('*/artifacts/manifest.json')):
            m=v.read(path)
            for k,s in m['models'].items():templates[k]=s
    base=Path('C:/Users/LG/Documents/D1Check_Decode_Resolution')
    images_root=base/'validation_inputs/canonical_png_v2_final'; image=v.read(images_root/'manifest.json')[0]
    sources=dict(classification=Path('C:/Users/LG/D1Check_Data/SIM-01_READY_20260919/downloads/efficientnet_lite0.tflite'),
                 detection=Path('C:/Users/LG/Documents/D1Check_GPU_Diag/run_20260920/host_golden/efficientdet_lite0.tflite'))
    pair_id=str(uuid.uuid4());order='AB' if int(v.sha(['v4-order',seed]),16)%2==0 else 'BA'
    recipes=[('cpu_lifecycle','lifecycle',['classification_CPU'],'standalone'),
             ('gpu_lifecycle','lifecycle',['classification_GPU'],'standalone'),
             ('resident_cpu_serial','resident_cpu_serial',['classification_CPU','detection_CPU'],'A'),
             ('resident_corun','resident_corun',['classification_CPU','detection_GPU'],'B')]
    if order=='BA':recipes[2:]=reversed(recipes[2:])
    entries=[]
    for name,configuration,keys,arm in recipes:
        sid=str(uuid.uuid4());inputs=output/'inputs'/sid;inputs.mkdir(parents=True)
        models={};slots=[];warm=[];requests=[]
        for i,key in enumerate(keys):
            spec=copy.deepcopy(templates[key]);task=spec['model']['task_id']
            spec['identity'].update(session_id=sid,created_utc=dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z'))
            spec['target']['apk_sha256']=apk_sha;spec['runtime']['cpu_threads']=1
            validate_manifest_data(spec);models[key]=spec
            data=sources[task].read_bytes()
            if v.digest(sources[task])!=spec['model']['sha256']:raise ValueError('pinned model changed')
            (inputs/spec['model']['filename']).write_bytes(data)
            with zipfile.ZipFile(sources[task]) as archive:label=archive.read(spec['model']['label_filename'])
            import hashlib
            if hashlib.sha256(label).hexdigest()!=spec['model']['label_sha256']:raise ValueError('label changed')
            (inputs/spec['model']['label_filename']).write_bytes(label)
            slots.append(dict(model_key=key,runtime_id=str(uuid.uuid4()),worker_id=0 if configuration=='resident_cpu_serial' else i))
            for _ in range(2):warm.append(dict(model_key=key,request_id=str(uuid.uuid4()),sample_id=image['sample_id'],priority='normal',offset_ms=0))
            requests.append(dict(model_key=key,request_id=str(uuid.uuid4()),sample_id=image['sample_id'],priority='urgent' if i==0 else 'normal',offset_ms=0))
        (inputs/image['filename']).write_bytes((images_root/image['filename']).read_bytes())
        (inputs/'anchors.json').write_bytes((base/'anchors.json').read_bytes())
        m=dict(protocol=v.PROTOCOL,schema_version=1,purpose='telemetry_smoke',session_id=sid,maximum_duration_ms=120000,
               apk_sha256=apk_sha,device_fingerprint=previous['fingerprint'],models=models,runtimes=slots,images=[image],
               requests=requests,warmup_requests=warm,warmup_per_runtime=2,configuration=configuration,seed=seed,
               thermal_gate=0,deadline_ns=None,memory_contract=v.MEMORY,
               paired=dict(pair_id=pair_id if arm!='standalone' else str(uuid.uuid4()),arm=arm,order=order))
        v.manifest(m)
        path=inputs/'manifest.json';path.write_bytes(v.canonical(m))
        entries.append(dict(name=name,session_id=sid,manifest=str(path.resolve()),manifest_sha256=v.digest(path),
                            input_hashes={p.name:v.digest(p) for p in sorted(inputs.iterdir())},no_op=v.no_op(m)))
    a=next(v.read(Path(e['manifest'])) for e in entries if e['name']=='resident_cpu_serial')
    b=next(v.read(Path(e['manifest'])) for e in entries if e['name']=='resident_corun')
    result=dict(protocol='telemetry-v4-smoke-plan-v1',apk_sha256=apk_sha,seed=seed,entries=entries,
                paired_dry_run=v.paired(a,b),formal_calibration=False,holdout=False,
                memory_rejection='safe host/JVM mock; no artificial device memory pressure')
    (output/'plan.json').write_bytes(v.canonical(result));return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--final-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--apk',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.final_root,a.output,a.apk),indent=2))


if __name__=='__main__':main()
