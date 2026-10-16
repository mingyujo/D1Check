"""Saved-data reporting only, including selected-versus-inherited paired results."""
import csv
import gzip
import json
import shutil
from collections import defaultdict
from pathlib import Path

import numpy as np

from tools import d1_atc_waitlink_report as helpers
from tools import d1_atc_waitlong_study as s


def report(root):
    root=Path(root);reg=s.check(root)
    rows=s.budget.read(root/"final_rows.json");cons=s.budget.read(root/"consumption.json");freeze=s.budget.read(root/"freeze.json")
    out=s.ROOT.parent.parent/"outputs"/s.budget.TASK;out.mkdir(parents=True,exist_ok=True)
    helpers.csvwrite(out/"final_rows.csv",rows)
    helpers.csvwrite(out/"summary_full.csv",helpers.summary(rows))
    helpers.csvwrite(out/"summary_primary.csv",helpers.summary(s.parent.primary(rows)))
    release=[row for row in rows if row["release_domain"]]
    helpers.csvwrite(out/"summary_release.csv",helpers.summary(release))
    roles=(*freeze["selections"],*freeze["inherited_selections"])
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
    for child in ("controls",*(f"seed{seed}" for seed in s.SEEDS)):
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
        role=f"{s.ARM}_{seed}";inherited=f"INHERITED4096_{s.ARM}_{seed}"
        for row in [x for x in rows if x["policy"]==role]:
            reference=by[row["condition"],inherited]
            item=dict(seed=seed,condition=row["condition"],family=row["family"],factor=row["factor"],primary=row["primary"],release_domain=row["release_domain"],
                      selected_episode=freeze["selections"][role]["episodes"],inherited_episode=4096)
            for key in (*s.SERVICE,"energy_j","peak_ap_c"):
                item["delta_"+key]=row[key]-reference[key] if row[key] is not None and reference[key] is not None else None
            paired.append(item)
    helpers.csvwrite(out/"selected_vs_inherited_paired.csv",paired)
    weights=out/"weights";weights.mkdir(exist_ok=True)
    mechanics=[]
    for seed in s.SEEDS:
        role=f"{s.ARM}_{seed}";child=root/f"seed{seed}"
        item=freeze["selections"][role]
        path=s.learner_path(child,seed,item["episodes"])
        if s.budget.digest(path)!=item["sha256"]:raise ValueError("selected weights changed")
        shutil.copy2(path,weights/path.name)
        base=s.learner_path(child,seed,4096);shutil.copy2(base,weights/base.name)
        latest=s.learning.Learner.load(s.learner_path(child,seed),s.deps(reg))
        origin=s.budget.read(child/"migration_receipt.json")
        mechanics.append(dict(seed=seed,total_episodes=latest.episodes,new_episodes=latest.episodes-4096,
            total_native_updates=len(latest.logs),new_native_updates=len(latest.logs)-512,
            total_Adam_steps=latest.steps,new_Adam_steps=latest.steps-origin["origin_Adam_steps"],pending=len(latest.pending),
            selected_episode=item["episodes"],selected_new_episodes=item["new_episodes"],
            inherited_selected=item["inherited_selected"],selected_sha=item["sha256"],
            inherited_sha=s.budget.digest(base)))
    helpers.csvwrite(out/"native_learning.csv",mechanics)
    for name in ("registration.json","inputs.json","namespace_receipt.json","migration_receipt.json","freeze.json","consumption.json","development_continuation.json","PROTOCOL_REGISTERED.md"):
        if (root/name).exists():shutil.copy2(root/name,out/name)
    if (root/"REGISTERED_SOURCE_TREE").exists():
        shutil.copytree(root/"REGISTERED_SOURCE_TREE",out/"REGISTERED_SOURCE_TREE",dirs_exist_ok=True)
    stage_rows=[]
    for seed in s.SEEDS:
        for path in sorted((root/f"seed{seed}").glob("stage*.json")):
            item=s.budget.read(path)
            stage_rows.append(dict(seed=seed,**{key:value for key,value in item.items() if not isinstance(value,(dict,list))}))
    helpers.csvwrite(out/"development_stages.csv",stage_rows)
    paired_summary=[]
    for seed in s.SEEDS:
        for scope in ("full","primary","release"):
            q=[row for row in paired if row["seed"]==seed and (scope=="full" or (scope=="primary" and row["primary"]) or (scope=="release" and row["release_domain"]))]
            item=dict(seed=seed,scope=scope,conditions=len(q),selected_episode=freeze["selections"][f"{s.ARM}_{seed}"]["episodes"])
            for key in (*s.SERVICE,"energy_j","peak_ap_c"):
                values=[row["delta_"+key] for row in q if row["delta_"+key] is not None]
                item.update({key+"_valid":len(values),key+"_wins":sum(v<0 for v in values),key+"_ties":sum(v==0 for v in values),key+"_losses":sum(v>0 for v in values),key+"_mean_delta":float(np.mean(values)) if values else None,key+"_worst_delta":max(values) if values else None})
            paired_summary.append(item)
    helpers.csvwrite(out/"selected_vs_inherited_summary.csv",paired_summary)
    text=["# 고정 WAIT1 장기 RL — 새 자료 확인 결과", "",
          f"신규 환경 {cons['environments']:,}회, 그 안에 신규 학습 {cons['learning']:,}episode가 포함됩니다. 환경 실패 {cons['failed']}회입니다.",
          "원11 terminal4096의3seed network/Adam/RNG를 정확히 이어 학습했습니다. 기존4096episode/history는 신규 소비로 계수하지 않습니다.",
          "새 학습2816case·개발176case·확인176case를 고정했고, 확인은6규칙+3선정+3계승4096의2112행입니다. 이전 확인 자료나 원실측을 늘린 것이 아닙니다.", "",
          "최종 모든 조건", "",helpers.table(helpers.summary(rows)), "",
          "선정과 계승4096의 seed별 조건 차이는 selected_vs_inherited_paired.csv에 전부 있습니다. 높은 episode의 모델을 선정한 사실만으로 추가학습 이득을 주장하지 않습니다.",
          "선정4096이면 해당 배포 모델의 신규 학습 이득은0이며, 별도로 실제 수행한 추가학습/부분stage 소비를 그대로 보고합니다.",
          "원 strict는 ε0·기존4참조·완료/서비스/P95/J/AP 계약입니다. developer stop의 .005J는 같은seed 계승 대비 개발 확대 기준이며 원 strict를 완화하지 않습니다.",
          "EFT0, Greedy는 독립 비교군 전용입니다. 실제AVAILABLE·비선점·CG_DC≤2·필요자원WAIT만 유지하며 NN에 미래queue/실현duration/J/AP를 넣지 않았습니다.",
          "CPU 분류4표본·고정plant·boundedK8와 finite자료 반복의 한계가 남습니다. 모바일 전체 작업등급·실기기 개선·자동 앱 채택을 주장하지 않습니다.",
          "등록된 규칙/모델/동결 및 실제 소비는 원장과 SHA가 근거입니다. final 뒤 재학습·재선정은0입니다."]
    text += ["", "모든 selected seed의 원 strict (full/primary) 및 추가 제안400ms release 적격성", ""]
    for role in freeze["selections"]:
        text.append(f"- {role}: full={verdict[role]['full']['promising']}, primary={verdict[role]['primary']['promising']}, release400ms={feasible[role]['feasible']}; 선정 누적episode={freeze['selections'][role]['episodes']}.")
    text += ["", "selected−동일seed inherited4096의 최종 paired 추가학습 비교", ""]
    for item in paired_summary:
        text.append(f"- seed{item['seed']}/{item['scope']}({item['conditions']}조건): P95 meanΔ={item['urgent_p95_ms_mean_delta']}, P95손해조건={item['urgent_p95_ms_losses']}, J meanΔ={item['energy_j_mean_delta']}, AP meanΔ={item['peak_ap_c_mean_delta']}; 다른서비스/조건손해는paired CSV에 모두 유지.")
    text += ["", "release400ms는 원strict와 별도이며 기존FAIL을PASS로 바꾸지 않습니다. 저장/판단 PC시간은 폰시간이나소비J로환산하지 않습니다.",
             "source/input/registration/freeze/선정PT SHA는manifest와REGISTERED_SOURCE_TREE, 전체raw SHA는raw_sha_receipts.csv, 실제env/학습/오류는executions 원장과consumption에결합됩니다."]
    (out/"RESULTS.md").write_text("\n".join(text)+"\n",encoding="utf8")
    manifest={path.relative_to(out).as_posix():s.budget.digest(path) for path in sorted(out.rglob("*")) if path.is_file() and path.name!="manifest.json"}
    s.write(out/"manifest.json",manifest)
    return dict(reported=True,output=str(out),selected=freeze["selected"],automatic_adoption=False)
