"""Offline design sensitivity, not a powered measurement plan or policy test."""
import argparse
import math
from pathlib import Path
from statistics import NormalDist, stdev

from tools import d1_policy_resolution as prior

ROOT = Path(__file__).resolve().parents[1]


def design_sensitivity(delta, sigma, pairs, alpha=.05, power=.8, bias_bound=0.):
    values = (delta, sigma, alpha, power, bias_bound)
    if any(v is None or not math.isfinite(v) for v in values) or delta <= 0 or sigma <= 0 or bias_bound < 0:
        raise ValueError('positive finite effect/dispersion; nonnegative bias')
    if isinstance(pairs, bool) or not isinstance(pairs, int) or pairs < 2 or not 0 < alpha < 1 or not .5 < power < 1:
        raise ValueError('pairs/risk scenario')
    z = NormalDist().inv_cdf(1-alpha/2)+NormalDist().inv_cdf(power)
    available = delta-bias_bound
    return dict(pairs=pairs, sessions=2*pairs, delta_j=delta, sigma_assumption_j=sigma,
        alpha=alpha, power_scenario=power, bias_bound_assumption_j=bias_bound,
        approximate_detectable_j=z*sigma/math.sqrt(pairs)+bias_bound,
        required_sigma_j=None if available <= 0 else available*math.sqrt(pairs)/z,
        illustrative_pair_count=None if available <= 0 else math.ceil((z*sigma/available)**2),
        fixed_observation_minutes=2*pairs*210/60,
        validated_power=None, recommended_pairs=None)


def load_source(source):
    source = Path(source)
    verification = prior.read(source/'verification.json')
    for name, expected in verification['files'].items():
        p = (ROOT/name).resolve()
        if not p.is_relative_to(ROOT) or prior.digest(p) != expected:
            raise ValueError('prior verified evidence identity')
    r = prior.read(source/'evaluation/evaluation.json')
    if [x['id'] for x in r['sessions']] != prior.IDS:
        raise ValueError('six-session denominator')
    for name, expected in r['source_files'].items():
        if prior.digest(source.parent/'separated_power_final'/name) != expected:
            raise ValueError('frozen original source identity')
    return r


def analyze(source, output):
    r = load_source(source)
    contrasts = [x for x in r['observed_contrasts'] if x['policy'] == prior.PAR]
    if len(contrasts) != 2 or [x['block'] for x in contrasts] != [0, 1]:
        raise ValueError('keep both original contrasts; no residual filtering')
    deltas = [x['observed_energy_delta_j'] for x in contrasts]
    sigma = stdev(deltas)
    counterfactuals = [x for x in r['same_initial_comparisons'] if x['policy'] == prior.PAR]
    target = abs(counterfactuals[0]['predicted_energy_delta_j'])
    if len(counterfactuals) != 6 or any(not math.isclose(abs(x['predicted_energy_delta_j']),target,abs_tol=1e-9) for x in counterfactuals):
        raise ValueError('single fixed model contrast, no favorable input search')
    scenarios = [design_sensitivity(target,sigma,n) for n in (4,8,16,32)]
    # Reductions are hypothetical design requirements, never measured benefits.
    reductions = [dict(hypothetical_sd_multiplier=f,
        **design_sensitivity(target,sigma*f,8)) for f in (1.,.5,.25,.1)]
    bias = [design_sensitivity(target,sigma,8,bias_bound=target*f) for f in (0.,.5,1.)]
    result = dict(version='policy-feasibility-pc-v1', source_sha256=prior.digest(Path(source)/'evaluation/evaluation.json'),
        source_freeze_sha256=r['source_freeze_sha256'], frozen_files=r['source_files'],
        chosen_input='existing confirmation mixed96/48:48/350ms; CPU vs PAR; no input search',
        observed_energy_deltas_j=deltas, descriptive_sd_j=sigma, contrast_count=2,
        prediction_contrast_error_sd_j=stdev(x['contrast_error_j'] for x in contrasts),
        target_j=target, target_origin='frozen point prediction, NOT minimum worthwhile effect',
        equivalent_120s_mean_power_mw=target/120*1000,
        same_initial_ap_peak_deltas_c=[x['predicted_peak_delta_c'] for x in counterfactuals],
        observed_ap_peak_deltas_c=[x['observed_peak_delta_c'] for x in contrasts],
        ap_sample_size=None, ap_sample_size_reason='different recorded query windows and initial/history; no stable variance or practical heat margin',
        scenarios=scenarios, hypothetical_reductions=reductions, hypothetical_bias=bias,
        decision='DO_NOT_SCALE_CURRENT_1_713J_CONFIRMATION',
        assumptions_validated=False, actual_required_pairs=None, run_ready=False,
        minimum_worthwhile_energy_j=None, allowed_peak_ap_increase_c=None,
        new_fits=0,new_forecasts=0,device_commands=0,experiment_ready=False,
        method_sources=['https://www.itl.nist.gov/div898/handbook/prc/section2/prc222.htm',
                        'https://www.itl.nist.gov/div898/handbook/prc/section3/prc311.htm'])
    output = Path(output);output.mkdir(parents=True,exist_ok=False)
    prior.write(output/'evaluation.json',result)
    prior.csv_write(output/'sensitivity.csv',scenarios)
    prior.csv_write(output/'hypothetical_reductions.csv',reductions)
    prior.csv_write(output/'hypothetical_bias.csv',bias)
    render(output,result)
    load_source(source)
    return result


def render(output,r):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    a=r['scenarios'];x=[t['pairs'] for t in a]
    axes[0].plot(x,[t['approximate_detectable_j'] for t in a],'o-',label='Illustrative sigma = historical 31.534 J')
    axes[0].axhline(r['target_j'],color='red',linestyle='--',label='Frozen prediction = 1.713 J')
    axes[0].set(xlabel='Hypothetical pairs (2 sessions each)',ylabel='Difference (J)',title='Known-sigma normal design scenario')
    axes[0].legend(fontsize=8)
    axes[1].plot(x,[t['required_sigma_j'] for t in a],'o-')
    axes[1].set(xlabel='Hypothetical pairs',ylabel='Required pair-difference SD (J)',title='Dispersion needed for 1.713 J')
    fig.suptitle('Assumptions unvalidated: not a sample-size recommendation or future bound')
    fig.tight_layout();fig.savefig(output/'feasibility.png',dpi=160);plt.close(fig)
    table=''.join(f'<tr><td>{x["pairs"]}</td><td>{x["sessions"]}</td><td>{x["approximate_detectable_j"]:.3f}</td><td>{x["required_sigma_j"]:.3f}</td><td>{x["fixed_observation_minutes"]:.0f}</td></tr>' for x in a)
    (output/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>CPU–PAR 판별 가능성</title>
<style>body{max-width:1000px;margin:2rem auto;font:17px/1.6 system-ui;padding:1rem}td,th{border:1px solid #bbb;padding:.5rem}table{border-collapse:collapse}img{width:100%}</style>
<h1>현재 1.713J 확인의 확대 반복은 권고하지 않음</h1>
<p>기존 차이 2개만으로 신뢰할 반복 수를 확정할 수 없습니다. 아래는 독립·정상성·알려진 분산을 가정한 양측 α=.05, 검정력 .8의 설계 민감도입니다. 실측 결과·정확도 PASS·실행 승인 아닙니다.</p>
<table><tr><th>가정 쌍</th><th>세션</th><th>가정상 검출 차이 J</th><th>1.713J에 필요한 SD J</th><th>고정 관측만 분</th></tr>'''+table+'''</table>
<img src="feasibility.png" alt="가정한 반복 수별 차이 판별 규모와 필요한 차분 변동">
<p>2,661쌍은 관측 SD를 미래 모집단 값으로 가정한 계산일 뿐 실제 필요 횟수가 아닙니다. 준비·회수·cleanup은 시간표에 포함되지 않습니다. 미래 분산·AP 허용 증가·최소 실용 절감량은 미확정입니다.</p>
<p><a href="../README.md">선정·근거·중단 결정·재현</a> · <a href="evaluation.json">수치와 미확정 값</a></p></html>''',encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();r=analyze(a.source,a.output)
    print(r['decision'])


if __name__=='__main__':main()
