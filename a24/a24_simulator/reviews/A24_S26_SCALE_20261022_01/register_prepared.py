"""Complete only pending registration; reuse all already prepared input bytes."""
import sys,ast
from pathlib import Path
H=Path(__file__).resolve().parents[2]/'experiments/a24_s26_scale_20261022';sys.path.insert(0,str(H))
from scale_common import *
def main():
    assert not O.exists() and not (H/'OPERATION.json').exists();inputs=read(H/'INPUTS.json');pf=read(V/'PREFLIGHT.json');assert len(inputs['cases'])==60 and pf['environment_START']==0
    write(V/'PREPARE_REGISTRATION_FAILURE.json',{'science_START':0,'prepared_banks_reused_without_regeneration':True,'reason':'Legacy dynamically executed module declares non-file _ops.py alias. Pin actual repository files; preserve virtual aliases as metadata.','new_fits':0})
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
    paths=[*H.glob('*.py'),H/'PROTOCOL.md',H/'INPUTS.json',V/'PREFLIGHT.json',CHECKPOINT,A/'results/A24_NN_URGENT_TIE_20261021_01/RISK_CALIBRATION.json',A/'results/A24_NN_URGENT_TIE_20261021_01/INFERENCE_CONTRACT.json',A/'experiments/common_count_20261021/INPUTS.json',A/'experiments/a24_s26_common_20261020/PROFILES.json',A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json',A/'experiments/a24_parallel_20261018/OPERATION.json',P.old.PORT/'SHAPE.json']
    virtual=[]
    for name,module in list(sys.modules.items()):
        p=getattr(module,'__file__',None)
        if p:
            p=Path(p).resolve()
            if p.is_relative_to(R) and p.suffix=='.py':
                if p.is_file():paths.append(p)
                else:virtual.append({'module':name,'synthetic_filename':str(p)})
    # These helpers are loaded from source strings into virtual aliases by the frozen loader.
    paths.extend(p for p in (A/'experiments/public_transfer_20261018').glob('*.py'))
    paths.extend(p for p in (A/'experiments/a24_s26_method_20261019').glob('*.py'))
    for item in inputs['cases']:
        for k in ['bank','public']:p=item[k];assert sha(R/p['path'])==p['sha256'];paths.append(R/p['path'])
    paths.extend([A/f'experiments/a24_duration_040_20261019/banks/D040_T600_P{i}_S160.BANK.json.gz' for i in [0,1]])
    for i,p in enumerate(CONTROLS):
        original=p.read_bytes();backup=V/f'CONTROL_BEFORE_{i}.bin';backup.write_bytes(original);base='../a24_simulator' if i<3 else '..';note=f'''## 2026-10-22 A24-S26-SCALE-01 · 同기준·입력규모 탐색 등록

사용자지시에따라[규약]({base}/experiments/a24_s26_scale_20261022/PROTOCOL.md)을등록했다. 선택한A24-05 BC/교사/기준선/물리동결,분류긴급.8초·탐지일반2초/두혼합/전체도착정시/입력별P95평균/고정관측창을S26에맞춘다. N256/512·묶음4/8/16·명목부하25/50%의10설정을DEV100평가에서선정하고미사용draw20평가로확인한다. 최대120EVAL/fit0·사전입력60개준비/과학START0이다.

기존완료/실패/모형/BC보존·새실측/학습/물리fit/ADB/게시0이다. CPU3 infer슬롯과미교정전력열/전이D_GPU가정은유지하며기기계수만다른동일엔진이라주장하지않는다. 준비import명충돌·가상파일명pin실패는fit/환경0에서보존·교정했고은행재생성0이다. 다음: 잠금아래유한평가→동결선정·별도확인→전량손해/검산/보고·봉인. HEAD ac3a5af+미커밋이다. 아래는이전이력이다.

''';p.write_bytes(note.encode('utf-8')+original)
    write(H/'OPERATION.json',{'schema':'A24_S26_SCALE_V1','unix':time.time(),'source_pins':[pin(p) for p in dict.fromkeys(paths)],'virtual_module_aliases':virtual,'checkpoint':pin(CHECKPOINT),'network_sha256':NETWORK,'max_scientific_units':120,'DEV':100,'CONF_selected':20,'new_fits':0,'new_measurements':0,'old_results_rerun':0,'automatic_retry':False,'adopted':False,'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'dirty':True,'authorization':'Same evaluation criteria; adjust A24 scale and find best metrics.','previous_local_derived':138095,'derived_local_cap':138215,'not_global_census':True})
    print(json.dumps({'state':'REGISTERED','inputs_reused':60,'source_pins':len(set(paths)),'scientific_START':0,'virtual_aliases':virtual}),flush=True)
if __name__=='__main__':main()
