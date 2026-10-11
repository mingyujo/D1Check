"""Add owned desktop result sections without discarding historical documents."""
import json
from pathlib import Path
import shutil

base=Path(__file__).resolve().parent
out=base.parent/'outputs'
repo=base/'repo'
result=json.loads((out/'result.json').read_text(encoding='utf-8'))
audit=json.loads((out/'final_verification.json').read_text(encoding='utf-8'))
policies=result['summary']
normal='/'.join(str(q['normal_failure']) for q in policies)
adam='/'.join(str(q['optimizer_steps']) for q in audit['states'])
active=result['timings']['run_active_seconds']/60
wall=result['timings']['run_wall_seconds']/60
cpu=result['timings']['run_cpu_seconds']/60
link='results/desktop_amount512_20261011/README.md'
label='## 2026-10-11 DESKTOP-AMOUNT-512-01'
def prepend_owned(path,section):
    raw=path.read_bytes();nl=b'\r\n' if b'\r\n' in raw else b'\n';sep=nl+nl
    title,body=raw.split(sep,1)
    if body.startswith(label.encode('utf-8')):
        next_section=body.find(nl+b'## ',1)
        assert next_section>=0
        body=body[next_section+len(nl):]
    content=section.strip().encode('utf-8').replace(b'\n',nl)
    path.write_bytes(title+sep+content+sep+body)

conclusion='원strict 최종gate 세 PPO 모두FAIL·새채택0' if not any(q['promising'] for q in result['gates'].values()) else '원strict gate 결과를 그대로 보존·자동채택0'
prepend_owned(repo/'docs/PROJECT_STATUS.md',f'''{label} — 원64→512 실제 연장·확인 완료

- [한국어보고·CSV·그림·오프라인화면]({link}): 세 모델 각448추가·총1344학습,2200/2300환경 전량완료·native오류0이다. 새48조건×7정책336행·개발24×3의72행 완료, 기능smoke3환경/72요청/학습0은별도다. 긴급실패0·일반실패(Band/Triton/Joint/Cost/PPO11/23/37)={normal}, {conclusion}이다.
- 세모델각512/64update/Adam{adam}, 원actor/critic/Adam/승수/공유round-robin RNG/source96/SHA/요청원장을검산했다. 정상중지473/25에서partial1/0/0·전체cursor/RNG exact복원후같은task재개·중복학습/clock초기화0이다. 실제wall/active/CPU={wall:.3f}/{active:.3f}/{cpu:.3f}분≤active240분·저장10분이다.
- parent500/192·프로젝트기저14735/3181 계승, 이번2200＋smoke3/1344로관련계보16938/4525다. 기존기본/strict/experiment_ready=false·원FAIL·사용자변경/원자료/다른worktree보존·휴대폰/ADB/실측/NPU/탐색0이다. 개발64→512 대응은이미본24이며새48에서64actor추가평가0·수렴/실기기절감미입증이다.
- 다음최대2: 결과공유, 별도설계승인전까지기존기준유지. task amount512_desktop_20261011_a 완료·자동확대0. 실행HEAD8175aac＋ZIP SHA4d7e0fcf…·전체검증영수증/원장/PT는local보존, 작은보고/설정/source만authorized branch에반영하며실제원격HEAD는별도확인영수증이다.''')
prepend_owned(repo/'docs/PROJECT_PLAN.md',f'''{label} — 승인된 데스크톱 학습량 실험 완료

- [실제결과]({link})의원V1/absolute-service v2 세learner64→512를동결ZIP에서실행했다. 각448추가/총1344학습·teacher448＋train1344＋dev72＋confirm336＝2200환경, 별도smoke3/학습0이다. 승인환경2300/학습1344·active240분/저장10분을확대하지않았다.
- source/보상/mask/목적/기한/지원/Adam/공유sampling RNG/parent소비보존, 실제경계중지·partial/RNG/cursor복원후같은task재개를검산했다. 전체48조건7정책원단위와이미본개발24의64→512 대응을구분했다.
- {conclusion}. 학습완료를수렴·목표절감·실기기/표면온도/온라인제어비용의입증으로승격하지않는다. 기존기본·strict·experiment_ready=false·과거소비/실험/원source유지, 기기/ADB/추가실측/새모형/탐색0이며남은상한자동사용0이다.''')
prepend_owned(repo/'docs/DECISIONS.md',f'''{label} — 학습량 연장 결과와 원판정 보존

- 확정된실행사실: 사용자가승인한원64 세모델의512연장·1344추가학습/2200환경·별도smoke3을동결설정과공유round-robin RNG로완료했다. [동일새48조건결과와상태/SHA]({link})를따른다. 실제정상중지후partial/세상태/RNG/cursor/active소비를보존해재개했으며optimizer/예산/clock초기화0이다.
- 판정: {conclusion}. 보상·학습량·개발자료의변화를새독립우위나512수렴으로대체하지않는다. 원기본/strict/experiment_ready=false와기존FAIL은유지하며휴대폰/ADB/새실측0이다. 이후제약/KPI정렬검토는별도설계·새명시승인·새독립자료가필요하다.''')
public=repo/'docs/results/desktop_amount512_20261011'
public.mkdir(exist_ok=True)
excluded={'full_state.zip','Stop-Task.ps1','Resume-Task.ps1','git_receipt.json','artifact_manifest.json'}
for p in out.iterdir():
    if p.is_file() and p.name not in excluded:
        shutil.copy2(p,public/p.name)
source=public/'host_scripts';source.mkdir(exist_ok=True)
for name in ('host_harness.py','verify_result.py','report_result.py','registry_check.py','pause_audit.py','environment_receipt.py','monitor.py','archive_result.py','record_project.py'):
    shutil.copy2(base/name,source/name)
(source/'README.md').write_text('이 source는 동결 정책을 수정하지 않는 host 검사·보고 도구 원형이다. 로컬 work/에 배치해 같은 상대경로의 bundle/, cpuenv/, repo/를 사용한다. 정책 실행 source는 Git 최신 tools가 아니라 SHA 검증한 원ZIP이다. 완료 task의 run/prepare 재실행·예산초기화는 금지한다. raw/PT/전체원장은 로컬 archive에만 보존한다.\n',encoding='utf-8')
print(json.dumps(dict(public_result_files=len(list(public.rglob('*'))),owned_docs_updated=['PROJECT_STATUS.md','PROJECT_PLAN.md','DECISIONS.md']),ensure_ascii=False))
