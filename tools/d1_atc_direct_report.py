"""Audit and report completed evidence only; never collect another environment."""
import argparse
import collections
import csv
import gzip
import html
import json
import math
import shutil
import statistics
import time
from pathlib import Path

import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from tools import d1_atc_direct_study as study
from tools import d1_atc_direct_ppo as learning
from tools import d1_atc_pilot_budget as ledger

plt.rcParams.update({"font.family":"Malgun Gothic","axes.unicode_minus":False,"font.size":10})


def csvwrite(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})


def timing(values):
    return dict(count=len(values),mean_ms=statistics.mean(values)*1000 if values else None,
                p95_ms=float(np.percentile(values,95))*1000 if values else None,
                max_ms=max(values)*1000 if values else None)


def replay_forward_timings(folder,raws,final,freeze):
    """Bounded posthoc pure-forward timing on saved inputs; no new environment/update."""
    torch.set_num_threads(1)
    rows=[]
    for seed in study.SEEDS:
        epoch=freeze["best_validation_epochs"][str(seed)]
        payload=torch.load(folder/"checkpoints"/f"seed{seed}_ep{epoch}.pt",map_location="cpu",weights_only=False)
        model=learning.ActorCritic();model.load_state_dict(payload["network"]);model.eval()
        snaps=[s for r in final if r["policy"]=="PPO"+str(seed) for s in raws[r["identity"]]["snapshots"] if "old_value" in s]
        chosen=snaps[::max(1,len(snaps)//100)][:100]
        arrays=[(torch.tensor(s["state"],dtype=torch.float32)[None],
                 torch.tensor(s["candidates"],dtype=torch.float32)[None],
                 torch.tensor(s["mask"],dtype=torch.bool)[None],s) for s in chosen]
        values=[];bins=collections.defaultdict(list)
        with torch.inference_mode():
            for state,vectors,mask,s in arrays[:10]:model(state,vectors,mask)
            for state,vectors,mask,s in arrays:
                begin=time.perf_counter();dist,value=model(state,vectors,mask);elapsed=time.perf_counter()-begin
                selected=s["base"] if dist.logits[0,s["base"]]==dist.logits[0].max() else int(dist.logits[0].argmax())
                if selected!=s["chosen"]:raise ValueError("frozen input replay selected a different action")
                queue=round(math.expm1(s["state"][1]*math.log(97)))+round(math.expm1(s["state"][2]*math.log(97)))
                values.append(elapsed);bins[queue].append(elapsed)
        rows.append(dict(policy="PPO"+str(seed),stage="pure_forward_saved_input_replay",scope="warmed posthoc replay; not live callback attribution",**timing(values)))
        rows.extend(dict(policy="PPO"+str(seed),stage="pure_forward_replay_by_queue",queue=q,**timing(v)) for q,v in sorted(bins.items()))
    return rows


def report(folder,out):
    folder=Path(folder);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if not ledger.read(folder/"cursor.json")["completed"]:raise ValueError("completed fixed evidence only")
    if (folder/"owner.lock").exists() or ledger.read(folder/"clock.json")["running_since"] is not None:
        raise ValueError("active run cannot be published as completed")
    reg=study.check(folder);b=ledger.Budget(folder);used=b.used()
    starts={r["identity"]:r for r in b.rows if r["event"]=="start"}
    if len(starts)!=used["environments"]:raise ValueError("duplicate consumed identity")
    completed={r["identity"] for r in b.rows if r["event"]=="completion"}
    failed={r["identity"] for r in b.rows if r["event"]=="failure"}
    if completed|failed!=set(starts) or completed&failed:raise ValueError("start/end ledger mismatch")
    native_rows=[];raws={};raw_receipts=[];planned=done=0
    for rp in sorted((folder/"rows").glob("*.json")):
        receipt=ledger.read(rp);row=receipt["row"];identity=row["identity"];path=folder/"items"/(identity+".json.gz")
        if ledger.digest(path)!=receipt["raw_sha256"]:raise ValueError("raw SHA mismatch")
        raw=json.loads(gzip.decompress(path.read_bytes()));study.audit_ledger(raw["result"])
        if row!=raw["row"] or len(raw["result"]["ledger"])!=row["planned"]:raise ValueError("row/raw denominator mismatch")
        planned+=row["planned"];done+=row["completed"]
        native_rows.append(row);raws[identity]=raw;raw_receipts.append(dict(identity=identity,sha256=receipt["raw_sha256"]))
    if len(native_rows)!=776:raise ValueError("registered776 successful study items expected")
    final=[r for r in native_rows if r["phase"]=="confirmation"]
    if len(final)!=336:raise ValueError("all48conditions x7roles required")
    gates={str(s):study.gate_rows(final,"PPO"+str(s),48) for s in study.SEEDS}
    if gates!=ledger.read(folder/"verdict.json"):raise ValueError("original epsilon0 verdict changed")
    freeze=ledger.read(folder/"freeze.json")
    states=[];logs=[]
    for seed in study.SEEDS:
        p=folder/"checkpoints"/f"seed{seed}_latest.pt";d=torch.load(p,map_location="cpu",weights_only=False)
        if d["episodes"]!=64 or d["pending"]:raise ValueError("terminal64 complete batch contract")
        if ledger.digest(p)!=freeze["terminal_sha"][str(seed)]:raise ValueError("terminal actor changed after freeze")
        states.append(dict(seed=seed,episodes=d["episodes"],updates=len(d["logs"]),Adam_steps=d["steps"],
            nonempty_Adam=bool(d["optimizer"]["state"]),actor_changed_updates=sum(x["actor_changed"] for x in d["logs"]),
            actor_gradient_max=max(x["actor_gradient_max"] for x in d["logs"]),multipliers=d["multipliers"].tolist(),
            checkpoint_SHA=ledger.digest(p),best_validation_epochs=freeze["best_validation_epochs"][str(seed)],
            action_RNG_SHA=study.payload_digest(d["action_rng"]),shuffle_RNG_SHA=study.payload_digest(d["shuffle_rng"])))
        logs.extend(dict(seed=seed,**x) for x in d["logs"])
    summary=[];decision_times=[];deltas=[];identity=[];by={(r["condition"],r["policy"]):r for r in final}
    semantics=collections.Counter()
    for role in study.ROLES:
        rr=[r for r in final if r["policy"]==role];times=[]
        stage=collections.defaultdict(list);qbins=collections.defaultdict(list)
        pair_seconds=resource_seconds=0.;opportunities=chosen_wait=0
        for row in rr:
            raw=raws[row["identity"]]
            times += [t["seconds"] for t in raw["callbacks"]]
            for t in raw["callbacks"]:qbins[t["queue"]].append(t["seconds"])
            for t in raw["stage_times"]:
                for key in ("atc_seconds","candidates_seconds","mask_seconds","encode_seconds","inference_seconds","total_seconds"):
                    stage[key].append(t[key])
            pair_seconds += sum(s["end_s"]-s["start_s"] for s in raw["segments"] if s["state"]=="classification_GPU+detection_CPU")
            for snap in raw["snapshots"]:
                opportunities+=sum(snap["mask"])>1
                chosen_wait+=snap["actions"][snap["chosen"]]["kind"]=="resource_wait"
                semantics["banks_same" if snap["ATC_EDD_same"] else "banks_different"]+=1
                semantics["legal_same" if snap["ATC_EDD_legal_actions_same"] else "legal_different"]+=1
                if snap["online_forecast_calls"]!=0:raise ValueError("online projection entered direct policy")
            for d in raw["result"]["decisions"]:
                if d.get("action_kind")=="resource_wait" and d.get("wait_until_ns"):
                    resource_seconds += max(0.,d["wait_until_ns"]-d["now_ns"])/1e9
        q=dict(policy=role,conditions=len(rr),planned=sum(r["planned"] for r in rr),
            completed=sum(r["completed"] for r in rr),incomplete=sum(r["incomplete"] for r in rr),
            urgent_failure=sum(r["urgent_failure"] for r in rr),normal_failure=sum(r["normal_failure"] for r in rr),
            mean_condition_P95_ms=statistics.mean(r["urgent_p95_ms"] for r in rr),
            mean_J120=statistics.mean(r["energy_j"] for r in rr),
            mean_peak_AP=statistics.mean(r["peak_ap_c"] for r in rr),
            whole_trace_callback=timing(times),parallel_seconds=pair_seconds,
            resource_timer_requested_seconds=resource_seconds,
            informative_snapshots=opportunities,chosen_wait_snapshots=chosen_wait)
        summary.append(q)
        decision_times.extend(dict(policy=role,stage=("selection_inference_and_reply" if key=="inference_seconds" else key),**timing(vals)) for key,vals in stage.items())
        decision_times.append(dict(policy=role,stage="all_callback_total",**timing(times)))
        decision_times.extend(dict(policy=role,stage="all_callback_by_actual_queue",queue=queue,**timing(vals)) for queue,vals in sorted(qbins.items()))
    decision_times.extend(replay_forward_timings(folder,raws,final,freeze))
    for s in study.SEEDS:
        role="PPO"+str(s)
        for i in range(48):
            r=by[i,role]
            for base in ("Band","Triton","EDD","Rule"):
                ref=by[i,base];diff=dict(condition=i,arrival_seed=r["arrival_seed"],family=r["family"],context=r["context"],policy=role,baseline=base)
                for k in ("incomplete","urgent_failure","normal_failure","urgent_p95_ms","energy_j","peak_ap_c"):diff["delta_"+k]=r[k]-ref[k]
                deltas.append(diff)
                identity.append(dict(condition=i,policy=role,baseline=base,
                    exact_schedule=study.schedule(raws[r["identity"]])==study.schedule(raws[ref["identity"]])))
    result=dict(status="completed_not_adopted",summary=summary,consumption=used,checkpoint_states=states,
        gates=gates,ATC_EDD_semantics=dict(semantics),selected_seed_before_confirmation=freeze["selected_seed"],
        actor_generation="fresh; native masked PPO;3 independent initialization/action/shuffle streams",
        simulator_scope="A24 frozen original service/energy plus v3 thermal-only; common point-profile transfer assumption",
        new_model_fit=0,device_commands=0,S26_learning=0,automatic_adoption=False,experiment_ready=False,
        policy_claim="no extra PPO advantage in this pilot; not convergence or general RL failure",
        before_device_use="AP model-plant observations/overhead need separate Android observation/export validation",
        AP_threshold=None,temperature_exceedance_time=None,threshold_reason="no registered AP/surface limit; no invented threshold",
        PC_time_is_phone_energy=False)
    study.write(out/"result.json",result);study.write(out/"verification.json",dict(status="PASS",
        base_HEAD=reg["base_head"],uncommitted_new_source=True,successful_study_items=len(raws),
        successful_study_planned=planned,successful_study_completed=done,raw_SHA_all_checked=True,
        phase_support_response_available_all_checked=True,immutable_budget=True,original_strict_epsilon=0,
        native_failed_host_reporting_invocations=len(failed),failed_identities=sorted(failed),
        rawfree_unit_tests=44,new_pure_contract_PPO_tests=11,S26_static_adapter_tests=2,
        PRIVATE_RAW_REQUIRED="not executed; not historical raw reproduction",
        resume=ledger.read(folder/"resume_receipt.json"),source_repairs=ledger.read(folder/"source_repairs.json"),
        publication_identity=ledger.read(folder/"publication_check.json"),
        consumption=used,checkpoint_states=states,new_fit=0,device_commands=0))
    csvwrite(out/"all_study_rows.csv",native_rows);csvwrite(out/"confirmation48.csv",final)
    csvwrite(out/"summary.csv",summary);csvwrite(out/"paired_condition_deltas.csv",deltas)
    csvwrite(out/"schedule_identity.csv",identity);csvwrite(out/"learning_updates.csv",logs)
    csvwrite(out/"decision_times.csv",decision_times);csvwrite(out/"raw_receipts.csv",raw_receipts)
    csvwrite(out/"execution_ledger.csv",b.rows)
    for name in ("registration.json","freeze.json","source_repairs.json","resume_receipt.json",
                 "preflight_repairs.json","s26_attached_coefficients_check.json"):
        shutil.copyfile(folder/name,out/name)
    shutil.copyfile(folder/"source_revisions/driver_repairs.diff",out/"driver_repairs.diff")
    s26=ledger.read(folder/"s26_audit.json")
    brief=dict(status=s26["status"],trees=s26["trees"],reasons=s26["reasons"],attachments=s26["attachments"],
        manifests=len(s26["sessions"]),request_journal_rows=sum(x["journal_rows"] for x in s26["sessions"]),
        seven_interval_adapter_pass=sum(x["interval_adapter_pass"] for x in s26["sessions"]),
        stress_attempts=sum(x["path"].startswith("R4S_blocks/") for x in s26["sessions"]),
        stress_missing_journals=[x["path"] for x in s26["sessions"] if x["path"].startswith("R4S_blocks/") and not x["request_journal_present"]],
        published_request_outputs_not_downloaded=True,new_fit=0,new_simulation=0,new_learning=0,device_commands=0)
    study.write(out/"s26_audit_summary.json",brief)
    make_figures(out,summary,deltas,logs,decision_times)
    make_readme(out,result,brief)
    make_html(out,result,final)
    return dict(status="PASS",new_simulation=0,new_learning=0,report_rows=len(final),
                promising={s:g["promising"] for s,g in gates.items()},consumption=used)


def save(fig,out,name):
    fig.savefig(out/(name+".png"),dpi=150,bbox_inches="tight")
    fig.savefig(out/(name+".svg"),bbox_inches="tight")
    plt.close(fig)


def make_figures(out,summary,deltas,logs,times):
    roles=[x["policy"] for x in summary];colors=["#466587"]*4+["#bd5c4a","#3a8c78","#b89245"]
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout="constrained")
    axes[0].bar(roles,[x["normal_failure"] for x in summary],color=colors);axes[0].set_title("일반 기한 실패 · 전체48조건");axes[0].set_ylabel("건")
    axes[1].bar(roles,[x["mean_condition_P95_ms"] for x in summary],color=colors);axes[1].set_title("긴급 응답 · 조건별P95 평균");axes[1].set_ylabel("ms")
    for ax in axes:ax.tick_params(axis="x",rotation=25)
    save(fig,out,"01_서비스와응답")
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout="constrained")
    for ax,key,title,unit in zip(axes,("mean_J120","mean_peak_AP"),("공통120초 에너지 · 동결 모형","35~180초 최고AP · 동결 모형"),("J","°C")):
        values=[x[key] for x in summary];ax.bar(roles,values,color=colors)
        padding=(max(values)-min(values))*.2 or .01;ax.set_ylim(min(values)-padding,max(values)+padding)
        ax.set_title(title);ax.set_ylabel(unit);ax.tick_params(axis="x",rotation=25)
    fig.suptitle("표면온도·실기기 절감 근거 아님 / 작은 차이를 확대해 표시")
    save(fig,out,"02_에너지와AP")
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout="constrained")
    for seed in study.SEEDS:
        rr=[x for x in logs if x["seed"]==seed]
        axes[0].plot([x["episodes"] for x in rr],[x["actor_gradient_max"] for x in rr],marker="o",label=str(seed))
        axes[1].plot([x["episodes"] for x in rr],[x["lambda_after"][3] for x in rr],marker="o",label=str(seed))
    axes[0].set_title("실제 actor gradient · 업데이트별 최대");axes[1].set_title("일반 실패 비용 승수")
    for ax in axes:ax.set_xlabel("누적 학습episode");ax.legend(title="학습seed")
    save(fig,out,"03_학습과승수")
    selected=[x for x in times if x["stage"]=="all_callback_total"]
    fig,ax=plt.subplots(figsize=(10,5),layout="constrained")
    ax.bar([x["policy"] for x in selected],[x["p95_ms"] for x in selected],color=colors)
    ax.set_title("PC 전체 판단 callback P95 · 폰 시간/에너지 아님");ax.set_ylabel("ms")
    save(fig,out,"04_PC판단시간")
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout="constrained")
    for j,role in enumerate(("PPO11","PPO23","PPO37")):
        rr=[x for x in deltas if x["policy"]==role and x["baseline"]=="Band"]
        axes[0].plot([x["condition"] for x in rr],[x["delta_energy_j"] for x in rr],marker=".",label=role)
        axes[1].plot([x["condition"] for x in rr],[x["delta_peak_ap_c"] for x in rr],marker=".",label=role)
    for ax in axes:ax.axhline(0,color="black",lw=1);ax.legend();ax.set_xlabel("고정 확인 조건")
    axes[0].set_title("조건별 Band 대비 J 차이");axes[0].set_ylabel("J")
    axes[1].set_title("조건별 Band 대비 AP 차이");axes[1].set_ylabel("°C")
    save(fig,out,"05_조건별비악화")


def make_readme(out,result,s26):
    rows=result["summary"];used=result["consumption"]
    lines=["# ATC→직접 PPO 데스크톱 파일럿 — 2026-10-11","",
        "**세 PPO 모두 원 strict FAIL, 새 정책 채택0이다.** A24 구현·기능 검증·3seed 작은 학습·새 확인을 완료했다. S26은 별도 감사와7구간 adapter 검증만 완료했고 품질/정밀도·시각·혼합 비용프로필 gate가 남아 학습0이다.","",
        f"새 task {ledger.TASK}: 환경{used['environments']}/1536, 실제학습{used['learning']}/384(A24 각seed64, S26 0), 누적실행활성{used['active_seconds']/60:.3f}분/240분, 마지막10분 저장 경계 유지. 설치/ADB/기기/새물리모형 적합0이다. 과거 amount512와 종료 예산·원FAIL은 보존한다.","",
        "## 같은 새48조건의 원단위 결과","",
        "4arrival seed×4부하×3문맥. 48독립 실측이 아니다. P95는 조건별P95의 평균이며 pooled P95가 아니다. J는0..120초, AP는35..180초 모형 내부채널이다.","",
        "|정책|완료/예정|긴급 실패|일반 실패|P95 평균 ms|J 평균|최고AP 평균 °C|","|---|---:|---:|---:|---:|---:|---:|"]
    for x in rows:lines.append(f"|{x['policy']}|{x['completed']}/{x['planned']}|{x['urgent_failure']}|{x['normal_failure']}|{x['mean_condition_P95_ms']:.3f}|{x['mean_J120']:.6f}|{x['mean_peak_AP']:.6f}|")
    lines += ["","PPO11은 같은 후보 Rule과 원단위 지표가 같다. PPO23/37은 Triton과 원단위 지표가 같다. 실제 일정 동일성은 schedule_identity.csv에48조건별로 별도 기록했다. 학습 update·gradient가 존재해도 규칙 이상의 추가 성능은 입증하지 못했다. 평균 개선으로 조건별 손실을 숨기지 않았고 epsilon0의 원 판정을 유지했다.","",
        "## 운영 구조와 정보 경계","",
        "작업별 FIFO 선두 → ATC top1 + 실행 가능한 선두/선두L0 보충 → CPU/GPU·CG_DC·자원WAIT → 물리mask → 고정 native PPO/규칙 → 사건 재판단. 최대요청2, 행동템플릿7, state90/action23이다. 실제 의미가 같은 자원WAIT는 중복 마스킹한다. candidate/action 생성·mask·encoder·복귀에서 큐 소진/미래AP/J/서비스 보호를 호출하지 않았다. 온라인 trap과 코드/원장 검사를 적용했다.","",
        "w_U2/w_N1,k2,구간EMA.1은 이 과제의 사전값이며 실제 지연비용/문헌 보편값이 아니다. 납기는1.5/6s, 지원C_CPU/C_GPU/D_CPU·CG_DC·비선점·실제AVAILABLE를 유지했다. AP/H/slow 중 현재 모형-환경 AP 관측만 신경망에 전달하며 숨은H/slow와 미래 도착/실현시간은 제외한다. 실기기AP 관측으로 검증 없이 바꿀 수 없다.","",
        f"ATC/EDD 비교: {result['ATC_EDD_semantics']}. 원장에는 보충 후bank 차이와 실제 유효행동의 차이를 구분했다. 유효행동이 계속 같다면 ATC 탐색을 중단하고 EDD 후보 + 직접 선택을 후속 대안으로 둔다. 현재 추가 튜닝0이다.","",
        "## 학습·중지재개·오류 기록","",
        "새 actor/critic/Adam과 시드별 초기화·행동sample·minibatch shuffle RNG를 사용했다. 각각64episode/8update, 실제Adam step·gradient·승수·normalizer는 learning_updates.csv/checkpoint metadata에 있다. gamma1, GAE없음, AP peak telescope 주보상과 J증분·미완료/긴급/일반 실패율·P95 비용이다. E/Q가중치1은고정, I/U/N만목표0의dual 갱신이다. 원단위KPI와 보상은 다르다.","",
        "29episode 경계에서3모델의 부분경험2/2/1·nonempty Adam·각RNG·전체cursor를 원자 저장했다. 별도 프로세스의 복원 payload 전량 일치 PASS를 확인했고 소비/clock/optimizer를 초기화하지 않았다. best-validation 후보와 terminal64를 따로 보존했으며 이번에는 모든seed의 개발 선택이64였다. 확인 후 seed 선택/재튜닝은 하지 않았다.","",
        "일반 구현 오류를 숨기지 않았다: 처음 schema 중복 keyword와 합성ATC 반례값을 순수 검증에서 수정(환경0), S26 CSV codec 철자 수정(환경0), 중지영수증 Settings JSON 체크섬 오류 수정(29학습 상태/소비 그대로), 첫Band 평가 후 결과이름 기록의 eager default 오류1환경을 원장에 실패로 보존하고 retry1을 추가했다. 뒤의 두 수정은 driver의 metadata/중지재개 단계 처리뿐이며 정책/학습식/가중치/Adam/RNG/등록 예산은 바꾸지 않았다. registration·원source/diff·effective SHA 영수증을 보존했다.","",
        "PRIVATE_RAW_REQUIRED 3suite는 실행하지 않았다. 원자료 없는44검사, 새계약/PPO11검사, S26 adapter2검사, 원동결demo3정책/288요청, 실행gate8은 별도 범위다. 단위시험의 합성gradient/수식 검증을 실제환경 학습episode로 세지 않는다.","",
        "## S26 추가자료의 적용","",
        f"고정3tree 및 사용자 추가4문서를 읽었다. {s26['manifests']}manifest, {s26['request_journal_rows']}관측요청의7구간→5phase 연결을 검산했다. R4S18attempt/유효14/요청원장 없는 실패4를 분리하고 준비·warmup을 성공으로 채우지 않았다. 추가 연결표의source/profile22개는바이트 또는LF 정규화일치다.","",
        "Q20의 품질은 quality-runner의 모델·20텐서·CompiledModel 계약에 귀속한다. 혼합request-runner나npu-runner의 포괄적 품질 승격이 아니다. GPU실제정밀도 보류를 유지하며 NPU/탐지GPU/3병행을 후보에 추가하지 않았다. 기존MobileNet/CPU4/chunk 열계수를 새CPU1 mixed로 전용하지 않았다.","",
        "대표R4C의 정기power_sample239와 admission 센서204를 재확인하고 적분대상은239로 분리했다. μA와mA를 섞지 않았다. HAL AP/SKIN을 분리했으며 before/after bracket 미관측을 보존한다. 앱/계수 바이트일치와 실제 정책 정확도/독립확인은 다르다. 첨부 홀드아웃 재현 스크립트는 실행하지 않았고 HTML/d1viewer 미제공·구모형 참조로 기록했다.","",
        "## 판정과 다음","",
        "기존앱 기본·strict·experiment_ready=false 유지. 새파일럿만 놓고 PPO11과Rule이 동률이면 단순한Rule을 우선하지만 Rule도Band 대비J/AP 손실이 있어 기본 교체 후보로 채택하지 않는다. 모든3seed 실패이므로 NoWait/열특징제거·128/512 확대·남은budget 자동사용0이다. 더 많은학습이 해결한다거나 RL일반실패/수렴이라고 결론내리지 않는다.","",
        "PC 판단시간의 평균/P95/최대·실제큐크기별값은 decision_times.csv다. live의selection_inference_and_reply는추론+선택+reply준비를포함한다. 순수forward는저장관측100개/seed·warm10의추론재생에서따로측정하고동결행동일치를확인했다(신규환경/학습0). live callback과posthoc replay를동일시간으로합치지않는다. callback밖관측/coldimport·설치는분리한다. 이시간은폰시간/에너지가아니다. 별도합성큰큐시험0이다.","",
        "## 파일·재현","",
        "[대시보드](index.html) · [사전등록](registration.json) · [검증](verification.json) · [전체CSV](all_study_rows.csv) · [48조건](confirmation48.csv) · [대응차이](paired_condition_deltas.csv) · [학습로그](learning_updates.csv) · [판단시간](decision_times.csv) · [S26 감사](s26_audit_summary.json)","",
        "공개source의 단위검증: python -B -X utf8 -m unittest tools.test_d1_atc_direct tools.test_d1_s26_mixed_audit -v. 종료run의check/report는 로컬raw·checkpoint가 있는PC에서만 실행한다: python -B -X utf8 -m tools.d1_atc_direct_study --run-root <기존run> check; python -B -X utf8 -m tools.d1_atc_direct_report --run-root <기존run> --output <보고폴더>. 이 명령은 신규환경/학습0이다.","",
        "완료task의register/run을 새예산으로 반복하지 않는다. raw/item/checkpoint는로컬에 보존하고공유는작은source/설정/CSV/그림/HTML/검증metadata만이다. 새실행은별도사용자범위·seed예약·유한계약이필요하다."
        ]
    (out/"README.md").write_text("\n".join(lines)+"\n",encoding="utf8")


def make_html(out,result,rows):
    table="<table><thead><tr><th>정책</th><th>완료/예정</th><th>일반 실패</th><th>P95 ms</th><th>J120</th><th>최고AP</th></tr></thead><tbody>"
    for r in result["summary"]:
        table+=f"<tr><td>{r['policy']}</td><td>{r['completed']}/{r['planned']}</td><td>{r['normal_failure']}</td><td>{r['mean_condition_P95_ms']:.3f}</td><td>{r['mean_J120']:.6f}</td><td>{r['mean_peak_AP']:.6f}</td></tr>"
    table+="</tbody></table>"
    data=json.dumps(rows,ensure_ascii=False).replace("</","<\\/")
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>D1Check ATC 직접PPO 파일럿</title>
<style>body{max-width:1350px;margin:32px auto;padding:0 22px;font:17px "Malgun Gothic",sans-serif;color:#193344;background:#f4f7fa}section{background:white;padding:24px;margin:22px 0;border-radius:12px}h1{font-size:32px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px;border-bottom:1px solid #d7e2eb;text-align:right}th:first-child,td:first-child{text-align:left}.warn{background:#fff0d3;padding:20px;border-radius:10px;line-height:1.7}img{max-width:100%;height:auto}select{font:inherit;margin:12px;padding:8px}.scroll{overflow:auto;max-height:650px}a{color:#176baa}</style>
<h1>ATC→직접 PPO: 새 파일럿 결과</h1><p class="warn"><b>세 PPO 모두 원 strict FAIL · 새 채택0.</b><br>791환경/192학습 · A24 3seed 각64 · S26 감사/adapter만, 학습0 · 기기/ADB0.<br>작은 모형 파일럿. 수렴·실기기 절감·표면온도 개선을 입증한 결과가 아닙니다.</p>
<section><h2>같은48조건 · 모든3seed</h2>'''+table+'''<p>P95는 조건별P95 평균. 모델 AP/J와 실제 폰 계측을 구분합니다.</p></section>
<section><h2>서비스와 비용</h2><img src="01_서비스와응답.png"><img src="02_에너지와AP.png"></section>
<section><h2>학습·조건별 비악화·PC 판단</h2><img src="03_학습과승수.png"><img src="05_조건별비악화.png"><img src="04_PC판단시간.png"></section>
<section><h2>전체48×7 원단위 행</h2><label>부하<select id="family"><option value="">전체</option><option>low</option><option>queue</option><option>burst</option><option>sustained</option></select></label><label>정책<select id="policy"><option value="">전체</option>'''+''.join("<option>"+r+"</option>" for r in study.ROLES)+'''</select></label><p id="count"></p><div class="scroll"><table><thead><tr><th>조건</th><th>부하/문맥</th><th>정책</th><th>완료/예정</th><th>긴급실패</th><th>일반실패</th><th>P95 ms</th><th>J</th><th>AP °C</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<p><a href="README.md">한국어보고</a> · <a href="verification.json">원장/SHA 검증</a> · <a href="confirmation48.csv">전체CSV</a> · <a href="s26_audit_summary.json">S26 미해결gate</a></p>
<script>const DATA='''+data+''';function draw(){const f=document.getElementById('family').value,p=document.getElementById('policy').value;const q=DATA.filter(r=>(!f||r.family===f)&&(!p||r.policy===p));document.getElementById('count').textContent=q.length+' / 336 행';document.getElementById('rows').innerHTML=q.map(r=>'<tr><td>'+r.condition+'</td><td>'+r.family+'/'+r.context+'</td><td>'+r.policy+'</td><td>'+r.completed+'/'+r.planned+'</td><td>'+r.urgent_failure+'</td><td>'+r.normal_failure+'</td><td>'+r.urgent_p95_ms.toFixed(3)+'</td><td>'+r.energy_j.toFixed(6)+'</td><td>'+r.peak_ap_c.toFixed(6)+'</td></tr>').join('');}document.getElementById('family').onchange=draw;document.getElementById('policy').onchange=draw;draw();</script></html>'''
    (out/"index.html").write_text(page,encoding="utf8")


def main():
    p=argparse.ArgumentParser();p.add_argument("--run-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    x=p.parse_args();print(json.dumps(report(x.run_root,x.output),ensure_ascii=False))


if __name__=="__main__":main()
