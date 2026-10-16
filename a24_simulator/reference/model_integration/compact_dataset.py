"""Lossless numeric model-input projection; full provenance stays in saved data.

Repeated receipts become exact JSON pointers, not fabricated or dropped data.
Only the explicitly registered descriptive/provenance fields are projected.
"""
import argparse
import hashlib
import json
from pathlib import Path

from runtime_guard import canonical, operation, pin, read, sha, write_new

REFERENCE_FIELDS = frozenset(('metadata_provenance', 'metadata_occurrences',
    'identical_republications', 'sensor_channels', 'invalid_events',
    'invalid_HAL_records', 'declared_status_versions', 'source_inventory',
    'raw_members', 'historical_saved_AP_prediction'))
GROUP_FIELDS = ('native_session_id','projection_content_sha256','raw_session_sha256')


def project(value, source_sha, pointer='', references=None):
    references = references if references is not None else []
    if isinstance(value, list):
        return [project(x, source_sha, pointer+'/'+str(i), references) for i,x in enumerate(value)]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        location = pointer+'/'+key.replace('~','~0').replace('/','~1')
        if key == 'provenance' or key in REFERENCE_FIELDS:
            reference = {'dataset_sha256':source_sha,'json_pointer':location,
                         'value_sha256':hashlib.sha256(canonical(item).encode()).hexdigest()}
            references.append(reference)
            if key == 'provenance' and isinstance(item,dict):
                result[key] = {k:item[k] for k in GROUP_FIELDS if k in item}
                result[key]['saved_full_reference'] = reference
            else:
                result[key+'_saved_reference'] = reference
        else:
            result[key] = project(item, source_sha, location, references)
    return result


def invariant(value):
    if isinstance(value,list):
        return [invariant(x) for x in value]
    if not isinstance(value,dict):
        return value
    out = {}
    for key,item in value.items():
        if key.endswith('_saved_reference') or key == 'saved_full_reference':
            continue
        if key == 'provenance':
            out[key] = {k:item[k] for k in GROUP_FIELDS if k in item} if isinstance(item,dict) else {}
        elif key not in REFERENCE_FIELDS:
            out[key] = invariant(item)
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--operation',required=True)
    args=parser.parse_args()
    with operation(args.operation,__file__) as (op,out):
        source=read(pin(op['dataset_pin']))
        refs=[]
        projected=project(source,op['dataset_pin']['sha256'],references=refs)
        before=hashlib.sha256(canonical(invariant(source)).encode()).hexdigest()
        after=hashlib.sha256(canonical(invariant(projected)).encode()).hexdigest()
        if before!=after:
            raise ValueError('Model numeric/identity/clock/owner/grouping input projection changed')
        write_new(out/'MODEL_INPUTS.json',projected)
        write_new(out/'REFERENCE_MAP.json',refs)
        write_new(out/'PROJECTION_RESULT.json',{'status':'NUMERIC_AND_GROUPING_INPUTS_IDENTICAL',
            'source_dataset_sha256':op['dataset_pin']['sha256'],'model_inputs_sha256':sha(out/'MODEL_INPUTS.json'),
            'before_invariant_sha256':before,'after_invariant_sha256':after,
            'exact_references':len(refs),'sessions':len(projected['sessions']),
            'source_data_modified':0,'model_fits':0,'new_environment':0,'HTTP':0})
    print(canonical({'status':'COMPLETE','output':str(out)}))


if __name__=='__main__':
    main()
