from pathlib import Path
import hashlib,json
V=Path(__file__).resolve().parent;old=V.parent/'A24_S26_SCALE_20261022_01'
record=[]
for name in ['audit.cjs','extract_series.cjs']:
    source=old/name;target=V/name;assert not target.exists();text=source.read_text(encoding='utf-8').replace('A24_S26_SCALE_20261022_01','A24_S26_JOINT_20261022_01').replace('experiments/a24_s26_scale_20261022','experiments/a24_s26_joint_20261022')
    if name=='audit.cjs':text=text.replace('starts.length<=120','starts.length<=40')
    # The time exporter is otherwise identical, but now includes 8 inputs in two settings.
    if name=='extract_series.cjs':text=text.replace('inputs:4','inputs:8')
    target.write_text(text,encoding='utf-8');record.append({'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'derived':name,'changes':'Output/experiment namespace; budget40; series8 inputs. Physics and request/policy checks unchanged.'})
(V/'AUDIT_PROVENANCE.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print('AUDIT_SOURCES_PREPARED')
