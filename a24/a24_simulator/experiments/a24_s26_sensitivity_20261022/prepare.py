import json,hashlib,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];A=R/'a24_simulator';O=A/'results/A24_S26_SENSITIVITY_20261022_01';V=A/'reviews/A24_S26_SENSITIVITY_20261022_01'
def pin(p):return {'path':p.relative_to(R).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def save(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
def main():
    assert not O.exists() and not (H/'OPERATION.json').exists();O.mkdir();V.mkdir(parents=True,exist_ok=True)
    paths=[H/'PROTOCOL.md',*H.glob('*.py')]
    for name in ['A24_S26_SCALE_20261022_01','A24_S26_JOINT_20261022_01']:
        paths.extend(A/'results'/name/f for f in ['RESULT.json','AUDIT_JS.json','AUDIT_PYTHON.json','FINAL_PROOF.json'])
    paths.extend([A/'experiments/a24_s26_scale_20261022/INPUTS.json',A/'experiments/a24_s26_joint_20261022/SELECTION.json',A/'experiments/a24_s26_joint_20261022/PROTOCOL.md'])
    save(H/'OPERATION.json',{'id':'A24-S26-SENS-03','source_pins':[pin(p) for p in dict.fromkeys(paths)],'new_environments':0,'new_fit':0,'new_measurements':0,'posthoc_saved_only':True,'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'dirty':True})
    controls=[R/'docs/PROJECT_STATUS.md',R/'docs/PROJECT_PLAN.md',R/'docs/DECISIONS.md',A/'docs/LATEST_EXECUTION_FILES.md'];record=[]
    for i,p in enumerate(controls):
        before=p.read_bytes();(V/f'CONTROL_BEFORE_{i}.bin').write_bytes(before);href='../results/A24_S26_SENSITIVITY_20261022_01/REPORT_KO.md' if i==3 else '../a24_simulator/experiments/a24_s26_sensitivity_20261022/PROTOCOL.md';block=f'## 2026-10-22 A24-S26-SENS-03 · 입력규모 민감도 분석 등록\n\n[규약/자료]({href}). 사용자 민감도 분석 지시에 따라 완료160행을 저장 재사용한다. N·도착률·묶음의 균형격자 유한차이/상호작용, 두혼합·draw·계산창·평가가중치에 대한 정책 우위 변화를 분석한다. 새환경/학습/fit/실측/기존완료 재시작0·기존평가기준/정책/모형 불변이다.\n\nDEV/CONF와 입력규모/물리계수 민감도를 구분하고 모든손해·미실행·동률·혼합별gate실패를 유지한다. 다음: 저장집계→독립JS 검산/그림→보고·기록/봉인. HEAD ac3a5af+미커밋. 아래는 이전이력이다.\n\n';p.write_bytes(block.encode()+before);record.append({'path':p.relative_to(R).as_posix(),'old_sha256':hashlib.sha256(before).hexdigest(),'new_sha256':pin(p)['sha256']})
    save(V/'CONTROL_REGISTRATION.json',record);print('SENSITIVITY_REGISTERED_SAVED_ONLY')
if __name__=='__main__':main()
