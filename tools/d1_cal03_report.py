"""PC-only final report. Requires both phases and a frozen confirmation report.
Never fits, launches ADB, changes source data, or overwrites output.
"""
import argparse, datetime, hashlib, json, re, statistics
from pathlib import Path


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ms(value):return f'{value/1e6:.6f}'


def main():
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
    root=args.root;plan_file=root/'timing_cal03_plan_v3/calibration_plan.json';plan=read(plan_file)
    fit_file=root/'timing_cal03_fit_v1.json';fit=read(fit_file)
    confirm_file=root/'timing_cal03_confirmation_v1.json';confirmed=read(confirm_file)
    assert confirmed['freeze_sha256']==sha(fit_file) and fit['plan_sha256']==sha(plan_file)==confirmed['plan_sha256']
    for data in (fit,confirmed):
        for file,digest in data['input_hashes'].items():assert sha(file)==digest,file
    result=dict(plan_sha256=sha(plan_file),fit_sha256=sha(fit_file),confirmation_sha256=sha(confirm_file),
                utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),phases={},sessions=[],screen_samples=0,
                screen_snapshot_elapsed_seconds=0.0,raw_hashes={},experiment_ready=False,performance_pass=None,
                interpretation='one independent session/cell/phase, four correlated requests; descriptive errors only')
    lines=['# CAL-03 보정·확인 결과','', '자료 적격성 확인과 예측 정확도 입증은 구분한다. 기존20null/experiment_ready=false 유지.', '',
           '## 소비량·환경·재사용','', '| 단계 | 시도/완료/실패/미시도 | 진단 | warmup | 재사용 쌍 |', '|---|---|---:|---:|---:|']
    for phase in ('development','confirmation'):
        base=root/'timing_cal03_run_v1'/phase;complete=read(base/'complete.json');assert complete['status']=='completed'
        assert read(base/'install_result.json')['status']=='installed'
        assert (base/'install_attempt.json').exists()
        for file in base.glob('*.json'):result['raw_hashes'][str(file)]=sha(file)
        phase_counts=dict(attempted=0,completed=0,failed=0,unattempted=0,requests=0,warmup=0,reuse_pairs=0,late_success=0)
        for entry in [e for e in plan['entries'] if e['phase']==phase]:
            folder=base/f"{entry['index']:02d}_{entry['session_id']}";art=folder/'artifacts'
            assert (folder/'attempt.json').exists() and (folder/'launch_attempt.json').exists() and not (folder/'error.json').exists()
            assert read(folder/'host_cleanup.json')['status']=='completed' and read(art/'cleanup.json')['status']=='completed'
            assert sha(art/'manifest.json')==entry['manifest_sha256'] and not (art/'failure_progress.jsonl').exists()
            rows=sorted(read(art/'requests.json'),key=lambda x:x['ordinal']);warm=read(art/'warmup_trace.json')
            assert len(rows)==4 and len(warm)==16 and all(x['terminal_status']=='succeeded' for x in rows)
            reuse=sum(x['lane_available_ns']<=y['actual_arrival_ns']<=y['dispatch_ns']<=y['execution_start_ns'] for x,y in zip(rows,rows[1:]))
            assert reuse==3
            screen=[read(p) for p in (folder/'screen_observations').glob('*.json')]
            assert all(x['status']=='sample_pass' and x['awake'] and x['interactive'] for x in screen)
            result['screen_samples']+=len(screen);result['screen_snapshot_elapsed_seconds']+=sum(x['host_end']-x['host_start'] for x in screen)
            battery=(folder/'before_battery.txt').read_text(encoding='utf-8');level=int(re.search(r'^\s*level:\s*(\d+)',battery,re.M)[1]);temp=int(re.search(r'^\s*temperature:\s*(\d+)',battery,re.M)[1])
            phase_counts['attempted']+=1;phase_counts['completed']+=1;phase_counts['requests']+=4
            phase_counts['warmup']+=sum(x.get('kind')=='end' and x.get('status')=='succeeded' for x in warm)
            phase_counts['reuse_pairs']+=reuse;phase_counts['late_success']+=sum(bool(x['late_success']) for x in rows)
            result['sessions'].append(dict(phase=phase,session_id=entry['session_id'],condition=[entry[k] for k in ('task','backend','priority')],valid_requests=4,independent_sessions=1,warmup_returned=8,lane_reuse_pairs=reuse,screen_samples=len(screen),battery_percent=level,battery_temperature_tenths_c=temp))
            for file in folder.rglob('*'):
                if file.is_file():result['raw_hashes'][str(file)]=sha(file)
        assert phase_counts['requests']==32 and phase_counts['warmup']==64
        starts=list(base.parent.glob(phase+'_preflight_*'));assert len(starts)==1
        # Windows directory creation UTC is approximate preflight start, not Android time.
        start=datetime.datetime.fromtimestamp(starts[0].stat().st_ctime,datetime.timezone.utc)
        end=datetime.datetime.fromisoformat(complete['utc'])
        phase_counts['host_utc_elapsed_approx_seconds']=(end-start).total_seconds()
        result['phases'][phase]=phase_counts
        lines.append(f"| {phase} | 8/8/0/0 | 32 | 64 | {phase_counts['reuse_pairs']} |")
    lines+=['',f"설치2회, 총16세션·진단64·warmup128·명시적추론192. retry/대체/추가0. 화면표본{result['screen_samples']}개 모두통과, host snapshot누적경과{result['screen_snapshot_elapsed_seconds']:.3f}초(순수CPU/기기부하시간 아님).",
            '밝기설정81/수동0/화면꺼짐18000000ms 유지 확인. app FLAG_KEEP_SCREEN_ON 및 기존설정만 사용했다. 표본 사이의연속awake를입증하지않으며, host관측이실행에미칠수있는영향을포함한수집조건이다.',
            f"host UTC(preflight폴더생성→phase complete) 기준 실행·cleanup 합계 약{sum(x['host_utc_elapsed_approx_seconds'] for x in result['phases'].values())/60:.2f}분; 승인상한121.5분. 이 값은Android 타임스탬프와빼지않았고벽시계점프부재를가정한근사다.",
            f"late success 합{sum(x['late_success'] for x in result['phases'].values())}건. 실패/거절/만료/미완료0; planned64 전체포함. deadline은진단용시나리오이며정책우수성근거아님.",'',
            '## 조건별 추정값과 확인 오차','', '각행: 개발n=1세션·4상관요청, 확인n=1세션·4상관요청. 원래단위ns, 아래표ms. 조건/구간을pooling하지않는다. 오차=확인관측−동결개발중앙값. 초과=오차>0의건수/4.', '',
            '| task/backend/priority | 구간 | 개발 median [min,max] ms | 확인 signed error [min,max] ms | 초과/4 |', '|---|---|---|---|---:|']
    short={'decision_to_dispatch_ns':'D→A','dispatch_to_start_ns':'A→S','start_to_output_ready_ns':'S→O','output_ready_to_persist_ns':'O→P','persist_to_lane_available_ns':'P→L'}
    for cell, fields in fit['estimates'].items():
        for field in short:
            f=fields[field]
            q=confirmed['errors'][cell][field];err=q['signed_error_ns']
            assert err==[x-f['median_ns'] for x in q['actual_ns']]
            assert q['overruns']==sum(x>0 for x in err) and len(err)==4
            lines.append(f"| {cell} | {short[field]} | {ms(f['median_ns'])} [{ms(f['min_ns'])}, {ms(f['max_ns'])}] | [{ms(min(err))}, {ms(max(err))}] | {q['overruns']} |")
    lines+=['','D=판단snapshot/A=dispatch/S=실행시작/O=output_ready/P=persist_complete/L=scheduler lane_available. urgent응답은D→O, normal은D→P. inference host API는S→O의부분구간이며GPU kernel 시간이아니다.',
            'N/A는예측목적의적용여부: urgent응답에O→P/P→L, normal응답에P→L, lane A→L에D→A는미적용. 실제관측을0으로치환하지않았다. 세션단위자료누락은이번에없으나적응형정책전용D→A는여전히missing이다. 상세용도는fit JSON에보존한다.', '',
            '## 판정과 다음 범위','', '개발적격성·확인자료적격성은통과했다. 예측정확도의숫자허용폭/coverage/우월성PASS는사전에설정하지않았으며 performance_pass=null이다. 큰오차를제외하거나확인자료로재조정하지않았다.',
            '40개관측슬롯은task×backend×priority별초기단독값이다. 기존20null을자동대체하지않는다. UNKNOWN_OVERRUN·experiment_ready=false 유지. 정책계산비용·병행간섭·미관측입력/부하·안정된tail·에너지/발열개선·과거정지원인해결은검증하지않았다.',
            '다음최소행동은PC에서고정단독추정계약의적용가능구간과UNKNOWN_OVERRUN 처리·adaptive D→A 미측정조건을정리하는것이다. 추가실측/정책평가는자동실행하지않는다.', '',
            f"plan SHA `{result['plan_sha256']}`",f"fit SHA `{result['fit_sha256']}`",f"confirmation SHA `{result['confirmation_sha256']}`",'',
            '재현: 이reproduce.py에 --root 외부root --output 새미존재폴더를지정한다. 원본/fit을수정하지않는다. fit/confirm 생성명령은실행문서에보존한다.']
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'SUMMARY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.output/'FINAL_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('phases','screen_samples','screen_snapshot_elapsed_seconds')},indent=2))

if __name__=='__main__':main()
