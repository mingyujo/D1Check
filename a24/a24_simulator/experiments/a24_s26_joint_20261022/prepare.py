from dominance_common import *

def main():
    assert not O.exists() and not (H/'OPERATION.json').exists();V.mkdir(parents=True,exist_ok=True)
    prior=read(OLDH/'OPERATION.json');verify(prior);old=read(OLDO/'RESULT.json');dev=[r for r in old['rows'] if r['condition']['role']=='DEV'];ranked=screen(dev);selected=[r for r in ranked if r['eligible']][:2];assert len(selected)==2
    ids=[r['setting'] for r in selected];allinputs=read(OLDH/'INPUTS.json');cases=[i for i in allinputs['cases'] if i['case']['condition']['role']=='CONF' and i['case']['condition']['setting'] in ids];assert len(cases)==8
    previous_identities={(r['bank']['sha256'],r['policy']) for r in old['rows']};checks=0
    for item in cases:
        bank=read(R/item['bank']['path']);public=read(R/item['public']['path'])['public'];c=item['case'];assert len(bank['jobs'])==len(public['requests'])==c['n'];checks+=1
        for p in MODES:assert (item['bank']['sha256'],p) not in previous_identities;checks+=1
        for j,q in zip(bank['jobs'],public['requests']):assert j['request_id']==q['request_id'] and j['deadline_ns']-j['scheduled_arrival_ns']==(800000000 if j['task']=='C' else 2000000000);checks+=1
    checkpoint=legacy.loadpt(CHECKPOINT);net=legacy.Learner(state=checkpoint);legacy.equal(net.snapshot(),checkpoint);assert checkpoint['network_sha256']==NETWORK;checks+=2
    write(H/'SELECTION.json',{'unix':time.time(),'source_result':pin(OLDO/'RESULT.json'),'reused_DEV':100,'candidates':ranked,'selected':selected,'selection_uses_new_CONFIRM':False,'historical_DEV_after_new_objective':True})
    write(H/'INPUTS.json',{'cases':cases,'selected_ids':ids,'max_new_EVAL':40,'new_fit':0,'original_input_manifest':pin(OLDH/'INPUTS.json')})
    write(V/'PREFLIGHT.json',{'status':'PASS','checks':checks,'new_environments_started':0,'prepared_cases':8,'max_EVAL':40,'new_fit':0,'resources':resources(True),'no_prior_completed_same_bank_policy':True})
    paths=[R/p['path'] for p in prior['source_pins']]+[H/'PROTOCOL.md',H/'INPUTS.json',H/'SELECTION.json',OLDO/'RESULT.json',OLDO/'FINAL_PROOF.json',V/'PREFLIGHT.json']+list(H.glob('*.py'))+list(V.glob('*.cjs'))+list(V.glob('*.py'))
    write(H/'OPERATION.json',{'schema':'A24_S26_JOINT_V1','unix':time.time(),'source_pins':[pin(p) for p in dict.fromkeys(paths)],'checkpoint':pin(CHECKPOINT),'network_sha256':NETWORK,'max_scientific_units':40,'reused_DEV':100,'new_fits':0,'new_measurements':0,'old_results_rerun':0,'automatic_retry':False,'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'dirty':True,'authorization':'User requests strict overall ontime and energy/AP superiority versus each FIFO EDF RR at S26 criteria; bounded verification of two preselected scales.','selected_ids':ids,'adopted':False})
    records=[]
    for i,p in enumerate(CONTROLS):
        before=p.read_bytes();(V/f'CONTROL_BEFORE_{i}.bin').write_bytes(before);href='../results/A24_S26_JOINT_20261022_01/REPORT_KO.md' if i==3 else '../a24_simulator/experiments/a24_s26_joint_20261022/PROTOCOL.md'
        title='진행 규약' if i!=3 else '예정 결과';block=f'## 2026-10-22 A24-S26-JOINT-02 · 정시·소비·온도 동시우위 확인 등록\n\n사용자 후속지시로 [{title}]({href})을 등록했다. 기존DEV100행 저장 재사용, 세 기준선 각각보다 합산 전체정시가 엄격히 높고 혼합별 정시 비악화·소비/AP 감소인 조건만 선별했다. 미응답/미완료0·혼합별 전체95/긴급99% 이상을 충족한 {", ".join(ids)}를 확인 전 고정했다. 기존모두100% 조건은 적격제외다.\n\n각4미사용합성입력×5정책, 최대40새EVAL·새학습/fit/실측0·동결A24-05/원물리 유지다. DEV는 사후 개발선정이고 기존draw 표본공유는 독립새실측이 아니다. 과학START0·기존완료 재시작0·자동후보추가/재시도0. 다음: 공유잠금 아래40회→두후보/모든손해 검산·보고→기록/봉인. HEAD ac3a5af+미커밋. 아래는 이전이력이다.\n\n';p.write_bytes(block.encode()+before);records.append({'path':p.relative_to(R).as_posix(),'old_sha256':hashlib.sha256(before).hexdigest(),'new_sha256':sha(p)})
    write(V/'CONTROL_REGISTRATION.json',{'files':records,'status':'PASS'});print(json.dumps({'state':'PREPARED','selected':ids,'checks':checks,'max_new_EVAL':40}),flush=True)
if __name__=='__main__':main()
