import datetime,json
from pathlib import Path
W=Path(__file__).resolve().parent.parent;R=W/'S26-D1Check/s26_simulator';H=R/'experiments/route_energy_v1';O=H/'artifacts/G001'
flowpath=W/'recovery/S26_ROUTE_ACTIVE_FLOW.json';flow=json.loads(flowpath.read_text(encoding='utf-8'));flow.update(status='RUNNING_COUNTED_REFERENCE_AND_BALANCED_TRAINING',main_session=34133,main_pid=json.loads((O/'START.json').read_text(encoding='utf-8'))['pid'],updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),do_next='Do not launch run.py again. Wait for420 receipts then saved-only audit/report. Preserve failures and consumed IDs. See OPERATION/PROTOCOL for CPU3 assumptions and absence of deadline guards.')
flowpath.write_text(json.dumps(flow,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
text='\n<!-- S26_ROUTE_CURRENT_BEGIN -->\n2026-10-18 사용자 지시로 `s26_simulator/experiments/route_energy_v1` 별도 실행 중(420예정/cap448). 경로선택 LP의85% 낙관적 하한은 기존CPU1 EDF대비20.981% 여유이나 납기를 완화한 하한이다. CPU3은 서비스작업을 남긴 미측정 병렬가정이며 추가코어 전력 감도를 별도 보고한다. 같은시나리오 단순EDF/ATC/보완ATC/원RL/에너지전용/3seed 보완RL을 비교한다. 기존자료만, 납기보호/NN뒤덮어쓰기/새실측/fit/업로드0. 진행/중복실행금지는 `../recovery/S26_ROUTE_ACTIVE_FLOW.json` 대신 워크스페이스 `recovery/S26_ROUTE_ACTIVE_FLOW.json`와 새receipts를 확인한다.\n<!-- S26_ROUTE_CURRENT_END -->\n'
for name in ['PROJECT_STATUS.md','PROJECT_PLAN.md']:
    p=R.parent/'docs'/name;s=p.read_text(encoding='utf-8');s=s.replace('\n',text,1);p.write_text(s,encoding='utf-8')
p=R.parent/'docs/DECISIONS.md'
with p.open('a',encoding='utf-8') as f:f.write('\n## 2026-10-18 — 경로 선택 여유·CPU 서비스 병렬가정·균형 보상 (사용자 지시로 실행 채택)\n\n기존 자료로 경로선택 완화하한을 먼저 계산한 뒤 무보호 RL을 별도 학습/평가한다. CPU 서비스1개 직렬 가정을3개까지 병렬화한 경우를 함께 비교하되 물리적 작업량은 삭제하지 않고 추가 코어전력의 미식별을 공개한다. TRAIN 참조 정규화·목적별 actor advantage RMS 균형·soft dual 납기 벌점을 사용하며 임박요청 강제/납기 행동mask/NN뒤규칙교체를 넣지 않는다. 기존실험/모형FAIL/실패원장/자료/PAUSED자동화는 보존한다. 근거는 `s26_simulator/experiments/route_energy_v1/PROTOCOL.json`과OPERATION,완료후새결과보고서다.\n')
print('ROUTE_RUNNING_STATE_RECORDED')
