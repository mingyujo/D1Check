"""Bind immutable A24 runtimes/materials to new plans OFFLINE; no device or claim.

Outputs always retain execution_authorized=false and DEVICE_UNVERIFIED. This
is preparation, not device registration, output quality approval or a START.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path

from d1_a24_laptop_prep import assemble_manifest, ledger_template
from d1_a24_laptop_validator import ValidationError, contained_file, load_json, sha256

KEYS = {'classification_CPU': 'C_CPU', 'classification_GPU': 'C_GPU',
        'detection_CPU': 'D_CPU', 'detection_GPU': 'D_GPU'}
MODEL_DIGESTS = {'C': '6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0',
                 'D': '40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58'}
LABEL_DIGESTS = {'C': 'e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f',
                 'D': 'f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2'}
GPU_CONFIGURATION = '58ee1a9dad76bb62d85dedae9204790863eacc7d8c3c0da404505616ca098068'
APPROVED_FILES = {
    'efficientnet_lite0.tflite': (18582189,MODEL_DIGESTS['C']),
    'efficientdet_lite0.tflite': (13836895,MODEL_DIGESTS['D']),
    'labels_without_background.txt': (10473,LABEL_DIGESTS['C']),
    'labels.txt': (661,LABEL_DIGESTS['D']),
    'anchors.json': (1438467,'e095e869203d5f5442583712e1546aac8f5112512b1a98925165fe17b455c3bc'),
    '00575b9132bb3746.png': (937799,'3e8b925feafbfe5fdd4efb9d7911f445a3212100fa73744f6fd855cf6160f1ab'),
}
TENSOR_DIGESTS = {'classification':'603328d02dfc2b1aa356b26b0f14b9e70f8cdb80609c89fd171bcf4c3ff85462',
                  'detection':'e1ce665bedf565285adccc4098433e338b9cdb08d681e0c0d424cae521e273ad'}
PACKAGE = 'com.example.d1check.benchmarkrunner.modelprobe'
MODEL_KEYS = {'identity','target','model','tensor','runtime','input','comparator','execution'}
TARGET_TEXT = ('manufacturer','model','soc','abi','android_release','build_fingerprint',
               'cpu_abi','cpu_features','gpu_vendor','gpu_renderer','gpu_driver','thermal_capability')
ZERO = dict(actual_device_commands=0, NN_calls=0, instrumentation_runs=0,
            claims=0, sessions_consumed=0, installs=0)


def encode(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + '\n').encode('utf-8')


def canonical_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
                                    allow_nan=False).encode()).hexdigest()


def exact_sha(value: object, description: str) -> str:
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):
        raise ValidationError(description+' requires exact lowercase SHA-256')
    return value


def source_models(source: dict) -> dict:
    models = source.get('models')
    if not isinstance(models,dict) or set(models) != set(KEYS):
        raise ValidationError('original manifest must expose exactly four original runtime cells')
    for old_key, new_key in KEYS.items():
        spec = models[old_key]
        if not isinstance(spec,dict) or set(spec) != MODEL_KEYS:
            raise ValidationError('original model-probe specification missing/extra fields')
        task,backend = new_key.split('_')
        expected_task = 'classification' if task=='C' else 'detection'
        m=spec['model']; r=spec['runtime']; t=spec['tensor']; c=spec['comparator']
        if (m.get('task_id')!=expected_task or m.get('sha256')!=MODEL_DIGESTS[task]
                or m.get('label_sha256')!=LABEL_DIGESTS[task]
                or spec['execution'].get('backend')!=backend):
            raise ValidationError('source task/backend/exact model or labels differ')
        if (r.get('litert_version')!='1.4.2' or r.get('cpu_threads')!=1
                or r.get('xnnpack') is not True or r.get('gpu_profile_id')!='gpu-fp32-strict-v1'
                or r.get('gpu_configuration_sha256')!=GPU_CONFIGURATION):
            raise ValidationError('source runtime differs from approved fixed CPU/strict GPU contract')
        size = 224 if task=='C' else 320
        if (t.get('input_count')!=1 or t.get('inputs',[{}])[0].get('shape')!=[1,size,size,3]
                or t['inputs'][0].get('dtype')!='FLOAT32'
                or t.get('normalization')!=('(RGB-127.0)/128.0' if task=='C' else '(RGB-127.5)/127.5')):
            raise ValidationError('source tensor/preprocessing differs')
        if (c.get('atol'),c.get('rtol'),c.get('decoded_score_atol'),c.get('decoded_box_atol_px')) != (1e-4,1e-3,1e-3,2.0):
            raise ValidationError('source output comparator tolerance changed')
    return models


def offline_target(apk_sha: str) -> dict:
    # Numeric device facts stay null. Parser admission intentionally requires a
    # later real identity binding, instead of fabricated RAM/API values.
    return dict(device_id='a24-laptop-device-unverified',package_name=PACKAGE,
                apk_sha256=apk_sha,adb_serial='DEVICE_UNVERIFIED',ram_bytes=None,
                api_level=None,**{key:'DEVICE_UNVERIFIED' for key in TARGET_TEXT})


def verify_materials(input_root: Path, binding: dict) -> dict:
    files=binding.get('files')
    if not isinstance(files,list) or len(files)!=6:
        raise ValidationError('exact six approved source files required')
    required={'efficientnet_lite0.tflite','efficientdet_lite0.tflite','labels.txt',
              'labels_without_background.txt','anchors.json','00575b9132bb3746.png'}
    if {x.get('filename') for x in files}!=required:
        raise ValidationError('approved source file names changed')
    answer={}
    for item in files:
        name=item['filename']; expected=exact_sha(item.get('sha256'),name)
        if (item.get('bytes'),expected)!=APPROVED_FILES[name]:
            raise ValidationError('material binding cannot replace approved bytes: '+name)
        file=contained_file(input_root,name)
        if sha256(file)!=expected or file.stat().st_size!=item.get('bytes'):
            raise ValidationError('source bytes/SHA mismatch: '+name)
        answer[name]={'bytes':item['bytes'],'sha256':expected,'logical_path':name}
    if (answer['efficientnet_lite0.tflite']['sha256']!=MODEL_DIGESTS['C']
            or answer['efficientdet_lite0.tflite']['sha256']!=MODEL_DIGESTS['D']
            or answer['labels_without_background.txt']['sha256']!=LABEL_DIGESTS['C']
            or answer['labels.txt']['sha256']!=LABEL_DIGESTS['D']):
        raise ValidationError('material metadata cannot change approved model/label hashes')
    return answer


def bind_session(bank_manifest: dict, models: dict, apk_sha: str,
                 materials: dict, binding: dict, source_sha: str, created: str) -> dict:
    sid=bank_manifest.get('session_id')
    if str(uuid.UUID(str(sid)))!=sid:
        raise ValidationError('new plan session ID must be canonical UUID')
    if any(spec['identity'].get('session_id')==sid for spec in models.values()):
        raise ValidationError('old runtime session ID cannot be reused')
    result=copy.deepcopy(bank_manifest)
    if result.get('consumed') is not False or result.get('registry_claim') is not None:
        raise ValidationError('only an unconsumed offline session may be bound')
    bound={}
    for old_key,new_key in KEYS.items():
        spec=copy.deepcopy(models[old_key])
        # Drop old identity and target completely; preserve immutable scientific
        # sections byte-equivalently under canonical JSON.
        spec['identity']=dict(schema_version=1,protocol_version='model-probe-v1',
                              session_id=sid,created_utc=created)
        spec['target']=offline_target(apk_sha)
        bound[new_key]=spec
    image=materials['00575b9132bb3746.png']
    tensors=binding['tensors']
    if any(tensors.get(task,{}).get('sha256')!=digest for task,digest in TENSOR_DIGESTS.items()):
        raise ValidationError('approved input tensor hashes cannot be changed')
    for request in result.get('requests',[]):
        task=request['task']; fulltask='classification' if task=='C' else 'detection'
        if (request.get('input_file')!='00575b9132bb3746.png'
                or request.get('input_sha256')!=image['sha256']
                or request.get('tensor_sha256')!=tensors[fulltask]['sha256']):
            raise ValidationError('bank input/tensor differs from approved binding')
    result.update(models=bound,apk_sha256=apk_sha,cpu_threads=1,
                  target_model='DEVICE_UNVERIFIED',device_fingerprint='DEVICE_UNVERIFIED',
                  device_status='DEVICE_UNVERIFIED',execution_authorized=False,mock=False,
                  experiment_ready=False,device_gate_verified=False,registry_claim=None,
                  runtime_scope='C_CPU_C_GPU_D_CPU_D_GPU_COMMON_RESIDENT_V1',
                  warmups_per_runtime=2,warmup_input=dict(input_file='00575b9132bb3746.png',
                    input_sha256=image['sha256'],c_tensor_sha256=tensors['classification']['sha256'],
                    d_tensor_sha256=tensors['detection']['sha256']),
                  resident_order=['C_CPU','C_GPU','D_CPU','D_GPU'],
                  permitted_request_runtime_keys=['C_CPU','C_GPU','D_CPU'],
                  source_files=copy.deepcopy(materials),
                  source_runtime_manifest_sha256=source_sha,
                  original_runtime_specification_sha256={KEYS[k]:canonical_sha(v) for k,v in models.items()},
                  tensor_binding_role='model-probe input fields are immutable raw seam descriptors; service requests use approved canonical PNG and tensor hashes',
                  device_binding_required=['actual serial/fingerprint/driver/RAM/API','APK/GPU/output gates','sensor/AP and initial gate','separate actual-start authorization'],
                  **ZERO)
    return result


def write_bound(source_file: Path, plan_root: Path, input_root: Path,
                apk_identity_file: Path, binding_file: Path, output: Path,
                *, copy_inputs: bool=False, source_plan: Path | None=None) -> dict:
    source=load_json(source_file); models=source_models(source)
    if source_plan is None:
        raise ValidationError('original plan SHA and runtime-manifest entry binding are required')
    old_plan=load_json(source_plan)
    matches=[entry for entry in old_plan.get('entries',[])
             if (source_plan.parent/entry.get('manifest','')).resolve()==source_file.resolve()]
    if len(matches)!=1 or matches[0].get('manifest_sha256')!=sha256(source_file):
        raise ValidationError('original plan does not bind exact source runtime manifest')
    plan_file=plan_root/'plan.json'; plan=load_json(plan_file); ledger_template(plan)
    binding=load_json(binding_file); materials=verify_materials(input_root,binding)
    apk=load_json(apk_identity_file); apk_sha=exact_sha(apk.get('apk_sha256'),'APK identity')
    if (apk.get('signature_verification')!='PASS' or apk.get('package')!=PACKAGE):
        raise ValidationError('exact statically verified APK package/signature required')
    exact_sha(apk.get('signer_certificate_sha256'),'APK certificate')
    if output.exists():
        raise FileExistsError('write-once bound package requires a new output directory')
    # Private material copies can only enter an ignored output subtree.
    if copy_inputs and not any(part.lower()=='output' for part in output.resolve().parts):
        raise ValidationError('model/image copies allowed only in a private output subtree')
    source_hash=sha256(source_file);created=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    manifests=[]
    for row in plan['sessions']:
        m=bind_session(assemble_manifest(plan_file,row['session_id']),models,apk_sha,
                       materials,binding,source_hash,created)
        m['source_commit']=plan['source_runtime_commit']
        # Sampling remains unfrozen until instrumentation/development verifies
        # actual sensor update/gap behavior. Preserve original polling proposal.
        period=source.get('power_sample_period_ms')
        if not isinstance(period,int) or isinstance(period,bool) or not 100<=period<=2000:
            raise ValidationError('original sensor polling proposal missing/out of supported range')
        m['sensor_period_ms']=period;m['sensor_sampling_status']='PROPOSED_FROM_SOURCE_NOT_FROZEN'
        manifests.append(m)
    output.mkdir(parents=True)
    destination=output/'session_manifests';destination.mkdir()
    records=[]
    for m in manifests:
        filename=m['session_id']+'.json';path=destination/filename;path.write_bytes(encode(m))
        records.append(dict(session_id=m['session_id'],path='session_manifests/'+filename,sha256=sha256(path)))
    if copy_inputs:
        copied=output/'approved_inputs';copied.mkdir()
        for name,item in materials.items():
            shutil.copyfile(contained_file(input_root,name),copied/name)
            if sha256(copied/name)!=item['sha256']:
                raise ValidationError('copied input verification failed')
    receipt=dict(schema='a24-laptop-offline-binding-v1',status='PC_BOUND_DEVICE_UNVERIFIED',
                 plan_sha256=sha256(plan_file),source_runtime_manifest_sha256=source_hash,
                 source_plan_sha256=sha256(source_plan) if source_plan else None,
                 material_binding_sha256=sha256(binding_file),apk_identity_sha256=sha256(apk_identity_file),
                 apk_sha256=apk_sha,session_count=len(manifests),manifests=records,
                 scientific_sections_unchanged=True,old_identity_targets_reused=False,
                 source_files=materials,private_inputs_copied=copy_inputs,
                 device_status='DEVICE_UNVERIFIED',execution_authorized=False,mock=False,**ZERO)
    (output/'binding_receipt.json').write_bytes(encode(receipt))
    return receipt


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ['source-runtime-manifest','plan-root','input-root','apk-identity','materials-binding','output']:
        parser.add_argument('--'+arg,type=Path,required=True)
    parser.add_argument('--source-plan',type=Path,required=True)
    parser.add_argument('--copy-inputs',action='store_true')
    a=parser.parse_args(argv)
    try:
        result=write_bound(a.source_runtime_manifest,a.plan_root,a.input_root,a.apk_identity,
                           a.materials_binding,a.output,copy_inputs=a.copy_inputs,source_plan=a.source_plan)
        print(json.dumps({k:result[k] for k in ['status','session_count','apk_sha256','device_status','execution_authorized',*ZERO]}))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps(dict(status='PC_BINDING_REJECTED_DEVICE_UNVERIFIED',reason=str(error),**ZERO)))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
