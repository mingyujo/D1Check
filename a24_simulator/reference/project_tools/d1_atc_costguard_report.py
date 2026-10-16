"""Saved-data reporting only, including selected-versus-inherited paired results."""
import csv
import gzip
import json
import shutil
from collections import defaultdict
from pathlib import Path

import numpy as np

from tools import d1_atc_waitlink_report as helpers
from tools import d1_atc_costguard_study as s


def report(root):
    root=Path(root);reg=s.check(root)
    rows=s.budget.read(root/"final_rows.json");cons=s.budget.read(root/"consumption.json");freeze=s.budget.read(root/"freeze.json")
    out=s.ROOT.parent.parent/"outputs"/s.budget.TASK;out.mkdir(parents=True,exist_ok=True)
    helpers.csvwrite(out/"final_rows.csv",rows)
    helpers.csvwrite(out/"summary_full.csv",helpers.summary(rows))
    helpers.csvwrite(out/"summary_primary.csv",helpers.summary(s.parent.primary(rows)))
    release=[row for row in rows if row["release_domain"]]
    helpers.csvwrite(out/"summary_release.csv",helpers.summary(release))
    roles=(*freeze["selections"],*freeze["origin_selections"])
    verdict={role:dict(full=helpers.strict(rows,role),primary=helpers.strict(s.parent.primary(rows),role)) for role in roles}
    s.write(out/"strict_verdict.json",verdict)
    helpers.csvwrite(out/"paired_win_tie_loss.csv",helpers.pairdiff(rows))
    feasible={}
    for role in dict.fromkeys(row["policy"] for row in rows):
        q=[row for row in release if row["policy"]==role]
        bad=[row["condition"] for row in q if row["completed"]!=row["planned"] or any(row[key] for key in
             ("urgent_failure","normal_failure","urgent_original_cap_failure","normal_original_cap_failure")) or row["urgent_p95_ms"] is None or row["urgent_p95_ms"]>400]
        feasible[role]=dict(feasible=not bad,proposed_urgent_P95_budget_ms=400,conditions=len(q),failed_conditions=bad,
            mean_J=float(np.mean([row["energy_j"] for row in q])) if all(row["energy_j"] is not None for row in q) else None,
            mean_AP=float(np.mean([row["peak_ap_c"] for row in q])) if all(row["peak_ap_c"] is not None for row in q) else None)
    s.write(out/"conditional_release_400ms.json",feasible)
    behavior=defaultdict(lambda:defaultdict(int));timing=defaultdict(list);queues=defaultdict(list);rawchecks=[];io=[]
    for child in ("controls","models"):
        folder=root/child
        for path in (folder/"rows").glob("*.json"):
            receipt=s.budget.read(path);rawpath=folder/"items"/(path.stem+".json.gz")
            if s.budget.digest(rawpath)!=receipt["raw_sha256"]:raise ValueError("raw SHA changed "+str(path))
            rawchecks.append(dict(worker=child,identity=path.stem,raw_sha256=receipt["raw_sha256"]))
        for path in (folder/"items").glob("confirmation_*.json.gz"):
            raw=json.loads(gzip.decompress(path.read_bytes()));s.parent.audit_ledger(raw["result"]);role=raw["row"]["policy"]
            for snap in raw["snapshots"]:
                if np.asarray(snap["state"]).shape!=(226,) or np.asarray(snap["candidates"]).shape!=(32,57):raise ValueError("saved ABI")
                if not snap["physical_mask"][snap["chosen"]] or snap["online_forecast_calls"]!=0:raise ValueError("saved physical mask/forecast")
                action=snap["actions"][snap["chosen"]];behavior[role]["decisions"]+=1;behavior[role][action["kind"]]+=1
                behavior[role]["teacher_overrides"]+=snap["chosen"]!=snap["base"]
                behavior[role]["nonhead"]+=snap["nonhead_selected"];behavior[role]["max_queue"]=max(behavior[role]["max_queue"],snap["queue_size"])
            for frame in raw["stage_times"]:
                for key in ("atc_seconds","candidates_seconds","mask_seconds","encode_seconds","inference_seconds","total_seconds","actual_total_seconds"):
                    if key in frame:timing[role,key].append(frame[key]*1000)
            for callback in raw["callbacks"]:queues[role,callback["queue"]].append(callback["event_to_dispatch_seconds"]*1000)
        if (folder/"checkpoint_io.jsonl").exists():
            io.extend(dict(seed=child,**json.loads(line)) for line in (folder/"checkpoint_io.jsonl").read_text("utf8").splitlines())
    helpers.csvwrite(out/"actual_behavior.csv",[dict(role=role,**value) for role,value in behavior.items()])
    helpers.csvwrite(out/"raw_sha_receipts.csv",rawchecks)
    helpers.csvwrite(out/"PC_timing.csv",[dict(role=role,stage=stage,count=len(value),mean_ms=float(np.mean(value)),P95_ms=float(np.quantile(value,.95)),max_ms=max(value)) for (role,stage),value in timing.items()])
    helpers.csvwrite(out/"PC_queue_timing.csv",[dict(role=role,queue=q,count=len(value),mean_ms=float(np.mean(value)),P95_ms=float(np.quantile(value,.95)),max_ms=max(value)) for (role,q),value in queues.items()])
    helpers.csvwrite(out/"checkpoint_io.csv",io)
    helpers.csvwrite(out/"checkpoint_io_summary.csv",[dict(seed=seed,count=len(q),mean_seconds=float(np.mean([x["seconds"] for x in q])),
        P95_seconds=float(np.quantile([x["seconds"] for x in q],.95)),max_seconds=max(x["seconds"] for x in q),
        max_checkpoint_bytes=max(x["bytes"] for x in q)) for seed in {x["seed"] for x in io} for q in [[x for x in io if x["seed"]==seed]]])
    paired=[];by={(row["condition"],row["policy"]):row for row in rows}
    for seed in s.SEEDS:
        for arm in s.ARMS:
            role=f"{arm}_{seed}"
            for row in [x for x in rows if x["policy"]==role]:
                for comparison,reference_role in (("CONTROL",f"CONTROL_{seed}"),("COST5",f"COST5_{seed}"),("origin4096",s.origin_role(seed))):
                    reference=by[row["condition"],reference_role]
                    item=dict(seed=seed,reward_arm=arm,comparison=comparison,condition=row["condition"],family=row["family"],factor=row["factor"],primary=row["primary"],release_domain=row["release_domain"])
                    for key in (*s.SERVICE,"energy_j","peak_ap_c"):item["delta_"+key]=row[key]-reference[key] if row[key] is not None and reference[key] is not None else None
                    paired.append(item)
    helpers.csvwrite(out/"reward_arm_paired.csv",paired)
    weights=out/"weights";weights.mkdir(exist_ok=True);mechanics=[];gates=[]
    for seed in s.SEEDS:
        for arm in s.ARMS:
            role=f"{arm}_{seed}";item=freeze["selections"][role];path=s.learner_path(root/"models",seed,item["episodes"],arm)
            if s.budget.digest(path)!=item["sha256"]:raise ValueError("selected weights changed")
            shutil.copy2(path,weights/path.name)
            latest=s.learning.Learner.load(s.learner_path(root/"models",seed,None,arm),s.deps(reg,arm))
            for log in latest.episode_logs:gates.append(dict(log.get("costguard",{}),seed=seed,reward_arm=arm,episode=log["episode"],family=log["row"]["family"],factor=log["row"]["factor"]))
            mechanics.append(dict(seed=seed,reward_arm=arm,episodes=latest.episodes,native_updates=len(latest.logs),Adam_steps=latest.steps,pending=len(latest.pending),selected_episode=item["episodes"],selected_sha=item["sha256"]))
        original=root/"origin_weights"/Path(reg["origin_checkpoints"][str(seed)]["path"]).name;shutil.copy2(original,weights/original.name)
    helpers.csvwrite(out/"native_learning.csv",mechanics)
    helpers.csvwrite(out/"gate_episode_audit.csv",gates)
    helpers.csvwrite(out/"gate_ratio_by_arm_seed.csv",[dict(seed=seed,reward_arm=arm,episodes=len(q),gate_pass=sum(x["gate_pass"] for x in q),gate_fail=sum(not x["gate_pass"] for x in q),pass_rate=sum(x["gate_pass"] for x in q)/len(q)) for seed in s.SEEDS for arm in s.ARMS for q in [[x for x in gates if x["seed"]==seed and x["reward_arm"]==arm]] if q])
    for name in ("registration.json","inputs.json","namespace_receipt.json","migration_receipt.json","freeze.json","consumption.json","development_continuation.json","PROTOCOL_REGISTERED.md"):
        if (root/name).exists():shutil.copy2(root/name,out/name)
    if (root/"REGISTERED_SOURCE_TREE").exists():
        shutil.copytree(root/"REGISTERED_SOURCE_TREE",out/"REGISTERED_SOURCE_TREE",dirs_exist_ok=True)
    stage_rows=[]
    for seed in s.SEEDS:
        for path in sorted((root/"models").glob("stage*.json")):
            for role,item in s.budget.read(path)["models"].items():
                if role.endswith("_"+str(seed)):stage_rows.append(dict(seed=seed,role=role,**{key:value for key,value in item.items() if not isinstance(value,(dict,list))}))
    helpers.csvwrite(out/"development_stages.csv",stage_rows)
    matched=[]
    for episode in s.completed_stages(root):
        rr=s.rows(root/"models",f"dev{episode}_");lookup={(row["condition"],row["policy"]):row for row in rr}
        for row in rr:
            arm,ss=row["policy"].rsplit("_",1)
            for reference_arm in ("CONTROL","COST5"):
                reference=lookup[row["condition"],reference_arm+"_"+ss]
                item=dict(episode=episode,seed=int(ss),reward_arm=arm,reference_arm=reference_arm,condition=row["condition"],family=row["family"],factor=row["factor"],primary=row["primary"],release_domain=row["release_domain"])
                for key in (*s.SERVICE,"energy_j","peak_ap_c"):item["delta_"+key]=row[key]-reference[key] if row[key] is not None and reference[key] is not None else None
                matched.append(item)
    helpers.csvwrite(out/"matched_stage_DEV_paired.csv",matched)
    paired_summary=[]
    for seed in s.SEEDS:
        for arm in s.ARMS:
            for comparison in ("CONTROL","COST5","origin4096"):
                for scope in ("full","primary","release"):
                    q=[r for r in paired if r["seed"]==seed and r["reward_arm"]==arm and r["comparison"]==comparison and (scope=="full" or (scope=="primary" and r["primary"]) or (scope=="release" and r["release_domain"]))]
                    item=dict(seed=seed,reward_arm=arm,comparison=comparison,scope=scope,conditions=len(q))
                    for key in (*s.SERVICE,"energy_j","peak_ap_c"):
                        vals=[r["delta_"+key] for r in q if r["delta_"+key] is not None]
                        item.update({key+"_wins":sum(v<0 for v in vals),key+"_ties":sum(v==0 for v in vals),key+"_losses":sum(v>0 for v in vals),key+"_mean_delta":float(np.mean(vals)) if vals else None,key+"_worst_delta":max(vals) if vals else None})
                    paired_summary.append(item)
    helpers.csvwrite(out/"reward_arm_paired_summary.csv",paired_summary)
    text=["# 고정 WAIT1 장기 RL — 새 자료 확인 결과", "",
          f"신규 환경 {cons['environments']:,}회, 그 안에 신규 학습 {cons['learning']:,}episode가 포함됩니다. 환경 실패 {cons['failed']}회입니다.",
          "9모델은3reward arm×3seed fresh paired 초기화이며12의learnedweights/Adam을재사용하지않습니다. 원4096은고정reference3군입니다.",
          "학습2816case·개발176case는12입력과참조4400개를SHA검증복사해재사용(복사신규환경0)하며새독립case수증가가아닙니다. 확인만새176case이고6규칙+9trained선정+3origin4096의3168행입니다. 이전확인자료나원실측을늘린것이아닙니다.", "",
          "최종 모든 조건", "",helpers.table(helpers.summary(rows)), "",
          "선정과 계승4096의 seed별 조건 차이는 reward_arm_paired.csv에 전부 있습니다. 높은 episode의 모델을 선정한 사실만으로 추가학습 이득을 주장하지 않습니다.",
          "선정은trained512이후모델이며 trainedCP0대체는없으며 실제수행한학습/부분stage소비를그대로보고합니다.",
          "원 strict는 ε0·기존4참조·완료/서비스/P95/J/AP 계약입니다. stop의 .005J는사전대응origin4096(1103←1013,1109←1019,1117←1021) 대비개발확대기준이며같은seed계승이아니고원strict를완화하지않습니다.",
          "EFT0, Greedy는 독립 비교군 전용입니다. 실제AVAILABLE·비선점·CG_DC≤2·필요자원WAIT만 유지하며 NN에 미래queue/실현duration/J/AP를 넣지 않았습니다.",
          "CONTROL은E/AP actor비용가중치1, COST5/GATED_COST5는5입니다. GATED는전량/units완료·선언/원U/N0·긴급P95≤같은caseRuleATC일때만원bonus를유지합니다. FAIL에서E는물리구간union의양의paired power차적분/10J, AP는35~120고정1초runningpeak차양의증가분/.1C를decision이후로투영합니다. AP는비가산peak proxy이고사후gate는서비스보장이아닙니다.",
          "CPU 분류4표본·고정plant·boundedK8와 finite자료 반복의 한계가 남습니다. 모바일 전체 작업등급·실기기 개선·자동 앱 채택을 주장하지 않습니다.",
          "등록된 규칙/모델/동결 및 실제 소비는 원장과 SHA가 근거입니다. final 뒤 재학습·재선정은0입니다."]
    text += ["", "모든 selected seed의 원 strict (full/primary) 및 추가 제안400ms release 적격성", ""]
    for role in freeze["selections"]:
        text.append(f"- {role}: full={verdict[role]['full']['promising']}, primary={verdict[role]['primary']['promising']}, release400ms={feasible[role]['feasible']}; 선정episode={freeze['selections'][role]['episodes']}.")
    text += ["", "동일seed CONTROL/사전대응origin4096 대비 보상arm 비교", ""]
    for item in paired_summary:
        text.append(f"- seed{item['seed']}/{item['reward_arm']}/{item['comparison']}/{item['scope']}({item['conditions']}조건): P95 meanΔ={item['urgent_p95_ms_mean_delta']}, P95손해조건={item['urgent_p95_ms_losses']}, J meanΔ={item['energy_j_mean_delta']}, AP meanΔ={item['peak_ap_c_mean_delta']}; 다른서비스/조건손해는paired CSV에 모두 유지.")
    text += ["", "release400ms는 원strict와 별도이며 기존FAIL을PASS로 바꾸지 않습니다. 저장/판단 PC시간은 폰시간이나소비J로환산하지 않습니다.",
             "source/input/registration/freeze/선정PT SHA는manifest와REGISTERED_SOURCE_TREE, 전체raw SHA는raw_sha_receipts.csv, 실제env/학습/오류는executions 원장과consumption에결합됩니다."]
    (out/"RESULTS.md").write_text("\n".join(text)+"\n",encoding="utf8")
    manifest={path.relative_to(out).as_posix():s.budget.digest(path) for path in sorted(out.rglob("*")) if path.is_file() and path.name!="manifest.json"}
    s.write(out/"manifest.json",manifest)
    return dict(reported=True,output=str(out),selected=freeze["selected"],automatic_adoption=False)
