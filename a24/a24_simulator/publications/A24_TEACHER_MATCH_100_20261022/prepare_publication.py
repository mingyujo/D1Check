"""Package saved evidence for GitHub. Never run a simulation or fit a model."""
import csv
import datetime
import hashlib
import io
import json
import pathlib
import subprocess

P = pathlib.Path(__file__).resolve().parent
R = P.parents[2]
A = R / 'a24_simulator'
O = A / 'results/A24_S26_MATCHED_BC_20261022_01'
STUDIES = [
    'A24_S26_MATCHED_BC_20261022_01',
    'A24_S26_SCALE_20261022_01',
    'A24_S26_JOINT_20261022_01',
    'A24_S26_SENSITIVITY_20261022_01',
]
CONTROLS = [
    'docs/PROJECT_STATUS.md', 'docs/PROJECT_PLAN.md', 'docs/DECISIONS.md',
    'a24_simulator/docs/LATEST_EXECUTION_FILES.md',
]


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, s):
    with p.open('x', encoding='utf-8', newline='\n') as f:
        f.write(s)


def csvwrite(name, rows):
    s = io.StringIO(newline='')
    w = csv.DictWriter(s, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    write(P / name, s.getvalue())


assert not (P / 'PUBLICATION.json').exists(), 'Already prepared; do not overwrite'
summary = read(O / 'SUMMARY.json')
primary = next(c for c in summary['cohorts'] if c['cohort'] == 'PRIMARY')
teacher = next(x for x in primary['overall'] if x['policy'] == 'TEACHER_MATCH')
assert teacher['ALL_on'] == teacher['ALL_n'] == 2048
assert teacher['U_on'] == teacher['U_n'] == 1280
assert teacher['N_on'] == teacher['N_n'] == 768
assert teacher['ALL_missing'] == teacher['ALL_incomplete'] == 0
contract = read(O / 'TEACHER_MATCH_CONTRACT.json')
assert not contract['uses_retrained_NN'] and not contract['new_WAIT_guard']

paths = set(CONTROLS)
for study in STUDIES:
    proofpath = A / 'results' / study / 'FINAL_PROOF.json'
    proof = read(proofpath)
    assert proof['status'] == 'PASS'
    paths.add(proofpath.relative_to(R).as_posix())
    for pin in proof['files']:
        paths.add(pin['path'])

# Preserve exact sealed document versions before adding the publication record.
snapshots = {}
sealed = {x['path']: x for x in read(O / 'FINAL_PROOF.json')['files']}
(P / 'sealed_controls').mkdir()
for name in CONTROLS:
    src = R / name
    assert digest(src) == sealed[name]['sha256'], name
    dst = P / 'sealed_controls' / pathlib.Path(name).name
    with dst.open('xb') as f:
        f.write(src.read_bytes())
    snapshots[name] = dst.relative_to(R).as_posix()

op = read(A / 'experiments/a24_s26_matched_bc_20261022/OPERATION.json')
for pin in op['source_pins'] + [op['checkpoint']]:
    assert digest(R / pin['path']) == pin['sha256'], pin['path']
    paths.add(pin['path'])
paths.update([
    'a24_simulator/experiments/a24_s26_method_20261019/audit.cjs',
    'a24_simulator/experiments/a24_nn_urgent_tie_20261021/audit.cjs',
])
# The previous finite studies are included to retain the finalizer's lineage checks.
for study in STUDIES:
    for base in [A / 'experiments', A / 'reviews']:
        if base.name == 'reviews':
            folder = base / study
        else:
            experiment = {
                STUDIES[0]: 'a24_s26_matched_bc_20261022',
                STUDIES[1]: 'a24_s26_scale_20261022',
                STUDIES[2]: 'a24_s26_joint_20261022',
                STUDIES[3]: 'a24_s26_sensitivity_20261022',
            }[study]
            folder = base / experiment
        for file in folder.rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
                paths.add(file.relative_to(R).as_posix())

keys = ['policy', 'inputs', 'ALL_n', 'ALL_on', 'ALL_on_pct', 'U_n', 'U_on',
        'U_on_pct', 'N_n', 'N_on', 'N_on_pct', 'ALL_missing', 'ALL_incomplete',
        'J', 'AP', 'U_P95', 'N_P95']
csvwrite('PRIMARY.csv', [{k: x[k] for k in keys} for x in primary['overall']])
cohorts = []
for c in summary['cohorts']:
    t = next(x for x in c['overall'] if x['policy'] == 'TEACHER_MATCH')
    cohorts.append({'cohort': c['cohort'], 'N_per_input': c['N'],
                    'nominal_load': c['load'], **{k: t[k] for k in keys}})
csvwrite('TEACHER_COHORTS.csv', cohorts)
comparisons = []
for ref in primary['overall'][:3]:
    comparisons.append({
        'policy': 'TEACHER_MATCH', 'reference': ref['policy'],
        'ALL_gain_pp': teacher['ALL_on_pct'] - ref['ALL_on_pct'],
        'predicted_energy_saving_pct': 100 * (ref['J'] - teacher['J']) / ref['J'],
        'mean_AP_reduction_C': ref['AP'] - teacher['AP'],
        'urgent_P95_change_s': teacher['U_P95'] - ref['U_P95'],
        'normal_P95_change_s': teacher['N_P95'] - ref['N_P95'],
    })
csvwrite('COMPARISONS.csv', comparisons)

labels = {
    'FIFO_DYN': 'FIFO', 'EDF_DYN': 'EDF', 'RR_DYN': 'RR',
    'TEACHER_OLD': '기존 교사', 'BC_OLD': '기존 BC',
    'TEACHER_MATCH': '**안전여유 보완 교사**',
    'TEACHER_GUARD': '대기 guard 추가 교사',
    'BC_GUARD_FROZEN': '기존 BC + 새 guard', 'BC_MATCHED': '재학습 BC + 새 guard',
}
lines = [
    '# A24: 안전여유 보완 교사규칙으로 주 평가 정시율 100%', '',
    '**롤링 + ATC + 교사규칙(`TEACHER_MATCH`)**이 같은 주 평가 입력에서 '
    '전체 **2,048/2,048건**, 긴급 **1,280/1,280건**, 일반 **768/768건**을 정시 처리했다. '
    '미응답·미완료는 모두 0건이다. **BC의 100% 성과가 아니다.**', '',
    'TRAIN 자료로 예측 오차의 안전여유만 다시 추정한 교사규칙이다. '
    '새 신경망과 이번에 추가한 WAIT guard는 사용하지 않았다. '
    '평가 전에 등록된 9개 비교 정책 중 하나이며 기본 정책으로 자동 채택하지 않았다.', '',
    '## 같은 주 평가 입력에서의 비교', '',
    '소비·AP는 입력별 평균, 정시율은 전체 도착 요청 기준이다. '
    '응답시간은 계획 도착부터 계산한다. P95는 입력별 nearest-rank P95의 산술평균이다.', '',
    '| 방법 | 전체 정시 | 긴급 정시 | 예측 소비 J* | 평균 AP ℃ | 긴급 P95 초 | 일반 P95 초 |',
    '|---|---:|---:|---:|---:|---:|---:|',
]
for x in primary['overall']:
    lines.append(f"| {labels[x['policy']]} | {x['ALL_on_pct']:.4f}% | "
                 f"{x['U_on_pct']:.4f}% | {x['J']:.3f} | {x['AP']:.3f} | "
                 f"{x['U_P95']:.3f} | {x['N_P95']:.3f} |")
lines += ['', '보완 교사규칙의 기준선 대비 변화:', '',
          '| 비교 기준 | 전체 정시 증가 %p | 예측 소비 감소 % | 평균 AP 감소 ℃ | 일반 P95 변화 초 |',
          '|---|---:|---:|---:|---:|']
for x in comparisons:
    lines.append(f"| {labels[x['reference']]} | +{x['ALL_gain_pp']:.4f} | "
                 f"{x['predicted_energy_saving_pct']:.4f} | {x['mean_AP_reduction_C']:.4f} | "
                 f"{x['normal_P95_change_s']:+.4f} |")
lines += [
    '', '일반 응답 P95는 세 기준선보다 길다. 정시율·예측 소비·평균 AP의 개선과 함께 이 상충을 보고해야 한다.', '',
    '## 평가 조건', '',
    '- 입력당 512건, 8건 묶음, A24 명목 부하 25%. 분류 비율 50%·75% 각각 새 draw 201·202, 총 4입력이다.',
    '- 도착률은 두 혼합에서 각각 약 2.612820·3.968551건/초다. 명목 25%는 실제 CPU 사용률이 아니다.',
    '- 분류 C는 긴급·기한 0.8초, 탐지 D는 일반·기한 2초다. 모든 도착 요청을 분모에 포함한다.',
    '- S26과 요청별 기한, 응답·정시 집계 기준, 관측창 규칙을 맞췄다. 기기 성능에 맞춰 요청 규모와 도착률을 조정했으므로 S26과 같은 난도를 뜻하지 않는다.',
    '- 도착 시작 35초, 공급 길이 N/도착률, 공급 끝+45초까지 배정, +60초 검열 진단, +90초 관측 종료. 소비는 0초~관측 종료, AP는 35초~관측 종료다.',
    '- 가상 CPU 추론 슬롯 3개·GPU 1개, ORIGINAL 물리모형, beta 0.25, 초기 AP 26℃를 동일 적용했다.', '',
    '## 다른 부하도 함께 공개', '',
    '| 구분 | 입력당 요청 | 명목 부하 | 전체 정시 | 긴급 정시 | 일반 정시 |',
    '|---|---:|---:|---:|---:|---:|',
]
for x in cohorts:
    lines.append(f"| {x['cohort']} | {x['N_per_input']} | {x['nominal_load']*100:.0f}% | "
                 f"{x['ALL_on']}/{x['ALL_n']} ({x['ALL_on_pct']:.4f}%) | "
                 f"{x['U_on_pct']:.4f}% | {x['N_on_pct']:.4f}% |")
lines += [
    '', '**100%는 표에 명시한 입력 조건의 관측 결과다.** 명목 부하 50%에서는 전체 정시율이 70.8984%로 내려간다. '
    '모든 부하의 기한 보장으로 해석하면 안 된다.', '',
    'J*는 미교정 전력모형의 예측 소비 적분값이다. 실기기 배터리 절감량으로 검증된 J가 아니다. '
    'CPU 슬롯·D_GPU 전이 가정, 정책 계산비용 제외, 같은 원실측 pool을 이용한 후속 합성 평가라는 한계가 있다. '
    '새로운 독립 기기 실측 검증은 아니다.', '',
    '## 원본·재현 자료', '',
    '- [원 실험 전체 보고서](../../results/A24_S26_MATCHED_BC_20261022_01/REPORT_KO.md): 9정책·세 조건·손해·BC 재학습 한계.',
    '- [전체 집계](../../results/A24_S26_MATCHED_BC_20261022_01/SUMMARY.json) · [전체 원자료 폴더](../../results/A24_S26_MATCHED_BC_20261022_01/).',
    '- [100% 정책 계약](../../results/A24_S26_MATCHED_BC_20261022_01/TEACHER_MATCH_CONTRACT.json) · [TRAIN 안전여유](../../results/A24_S26_MATCHED_BC_20261022_01/RISK_CALIBRATION.json).',
    '- [평가 규약](../../experiments/a24_s26_matched_bc_20261022/PROTOCOL.md) · [동결 입력·코드 핀](../../experiments/a24_s26_matched_bc_20261022/OPERATION.json) · [교사 정책 코드](../../experiments/a24_nn_urgent_tie_20261021/policy.py).',
    '- [독립 검산 코드](../../reviews/A24_S26_MATCHED_BC_20261022_01/) · [최종 봉인](../../results/A24_S26_MATCHED_BC_20261022_01/FINAL_PROOF.json).',
    '- [주 평가 CSV](PRIMARY.csv) · [기준선 대비 변화 CSV](COMPARISONS.csv) · [보조·고부하 CSV](TEACHER_COHORTS.csv).',
    '- [게시 파일·출처·해시](PUBLICATION.json). 직전 규모 탐색·동시우위 확인·민감도 분석은 검산 계보를 보존하기 위해 함께 포함했다.', '',
    '완료된 105단위(환경 102·안전여유 추정 1·BC fit 2)는 105 COMPLETE·FAIL 0이다. '
    '이번 게시는 저장된 결과만 사용하며 새 실험·학습·기존 완료 재시작은 0회다. '
    '기존 JS 13,716,658검사·Python 119,585검사·NN 27,767선택 검증을 보존했다.', '',
    '체크아웃 후 아래 명령은 게시 파일 해시·원본 봉인·저장 원자료의 주 평가 지표를 읽기 전용으로 확인한다. '
    '시뮬레이션이나 학습을 다시 실행하지 않는다.', '',
    '```powershell',
    'python a24_simulator/publications/A24_TEACHER_MATCH_100_20261022/verify_publication.py',
    '```', '',
    '기존 봉인 당시의 네 제어문서는 `sealed_controls/`에 원래 바이트로 보존했다. '
    '현재 STATUS·LATEST에는 게시 안내를 추가했으므로 원 봉인 검사는 보존본을 사용한다. '
    '과거 `adopted:false`·`게시0` 기록은 당시 상태이며 이번 명시적 게시 요청으로 소급 변경하지 않았다.', '',
]
write(P / 'README.md', '\n'.join(lines))

status = ('## 2026-10-22 A24 100% 교사규칙 결과 GitHub 게시\n\n'
          '[게시 정본](../a24_simulator/publications/A24_TEACHER_MATCH_100_20261022/README.md). '
          '사용자 요청으로 TEACHER_MATCH 주 평가 전체2048/2048·긴급1280/1280·일반768/768 정시 결과와 원자료·코드·검산 계보를 게시한다. '
          '이는 안전여유 보완 교사규칙이며 BC 100%가 아니다. 고부하 전체70.8984%·일반P95 증가도 공개한다. '
          '완료 실험 재시작/새학습0, 기존 봉인 네 제어문서는 게시 폴더에 원바이트 보존했다. '
          '검증 대상은 PUBLICATION.json의 파일 해시다. 아래는 게시 전 완료/등록 이력이다.\n\n')
latest = ('## 2026-10-22 · 100% 교사규칙 게시 자료\n\n'
          '[바로 보기](../publications/A24_TEACHER_MATCH_100_20261022/README.md): '
          'S26 평가기준·N512/묶음8/명목25%의 TEACHER_MATCH 전체2048/2048 정시. '
          'BC와 구분한 비교표·모든 부하·원자료·재현 코드·검산 계보·게시 해시를 포함한다. '
          '실험 재시작0. 아래는 게시 전 이력이다.\n\n')
for path, prefix in [(R / CONTROLS[0], status), (R / CONTROLS[3], latest)]:
    old = path.read_bytes()
    assert not old.startswith(b'\xef\xbb\xbf')
    path.write_bytes(prefix.encode('utf-8') + old)

paths.update(p.relative_to(R).as_posix() for p in P.rglob('*') if p.is_file())
paths.add((P / 'verify_publication.py').relative_to(R).as_posix())
pins = []
for name in sorted(paths):
    p = R / name
    assert p.is_file(), name
    assert p.stat().st_size < 100 * 1024**2, ('GitHub blob limit', name)
    assert p.suffix.lower() not in {'.tflite', '.apk', '.onnx', '.exe'}, name
    pins.append({'path': name, 'sha256': digest(p), 'bytes': p.stat().st_size})
manifest = {
    'id': 'A24_TEACHER_MATCH_100_20261022', 'recorded_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'base_HEAD': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R, text=True).strip(),
    'branch': 'codex/a24-simulator-handoff-20261016',
    'authorization': 'User explicitly requested publishing the 100% result to GitHub and its path.',
    'policy': 'TEACHER_MATCH', 'is_BC_100_percent': False,
    'new_simulations': 0, 'new_fits': 0, 'completed_experiments_restarted': 0,
    'primary_on_time': {'ALL': [2048, 2048], 'U': [1280, 1280], 'N': [768, 768]},
    'sealed_control_snapshots': snapshots,
    'included_studies': STUDIES, 'files': pins,
    'excludes_own_bytes': True,
}
write(P / 'PUBLICATION.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
pathspec = R / '.git/A24_TEACHER_MATCH_100_PATHS.txt'
pathspec.write_text('\n'.join([x['path'] for x in pins] + [(P / 'PUBLICATION.json').relative_to(R).as_posix()]) + '\n', encoding='utf-8')
print(json.dumps({'prepared': True, 'files': len(pins) + 1,
                  'bytes': sum(x['bytes'] for x in pins), 'pathspec': str(pathspec)}, ensure_ascii=False))
