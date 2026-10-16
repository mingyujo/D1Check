"""Descriptive diagnostics shared by saved and counterfactual A24 reports."""
from __future__ import annotations

import math


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def quantile(values, probability):
    values = sorted(float(x) for x in values if finite(x))
    if not values:
        return None
    index = (len(values)-1) * probability
    left = int(math.floor(index))
    right = min(len(values)-1, left+1)
    return values[left] + (values[right]-values[left]) * (index-left)


def error_summary(values):
    values = [float(x) for x in values if finite(x)]
    return {'n': len(values), 'MAE': sum(abs(x) for x in values)/len(values) if values else None,
            'RMSE': math.sqrt(sum(x*x for x in values)/len(values)) if values else None,
            'bias': sum(values)/len(values) if values else None,
            'maximum_absolute': max(map(abs, values), default=None),
            'P95_absolute': quantile([abs(x) for x in values], .95)}


def request_metrics(requests, cutoff_s=180.):
    """Every planned request remains in its denominator, including missing32."""
    result = {}
    for cohort in ('ALL', 'U', 'N'):
        rows = list(requests) if cohort == 'ALL' else [x for x in requests if x.get('priority') == cohort]
        completed, deadline_met, late, censored = [], 0, 0, []
        for row in rows:
            response = row.get('response_s')
            deadline = row.get('deadline_s')
            arrival = row.get('scheduled_arrival_s')
            if finite(response) and finite(arrival):
                completed.append(response-arrival)
                if finite(deadline):
                    deadline_met += int(response <= deadline)
                    late += int(response > deadline)
            else:
                censored.append(max(0., cutoff_s-deadline) if finite(deadline) else None)
        result[cohort] = {'planned': len(rows), 'responded': len(completed),
                          'incomplete': len(rows)-len(completed), 'on_time': deadline_met,
                          'late_completed': late,
                          'service_fraction': deadline_met/len(rows) if rows else None,
                          'response_P95_s': quantile(completed, .95),
                          'response_mean_s': sum(completed)/len(completed) if completed else None,
                          'unresponded_tardiness_lower_bounds_s': censored,
                          'zero_denominator_is_success': False}
    return result


def ap_window(points, start_s=35., end_s=180., max_gap_s=5.):
    """Past-sample ZOH only; gap failures remain null, including the tail."""
    points = sorted((float(x['t_s']), float(x['ap_c'])) for x in points
                    if finite(x.get('t_s')) and finite(x.get('ap_c')))
    left = [x for x in points if x[0] <= start_s]
    if not left or start_s-left[-1][0] > max_gap_s:
        return {'status': 'UNKNOWN_START_COVERAGE', 'mean_C': None, 'peak_C': None, 'end_C': None}
    anchors = [left[-1]] + [x for x in points if start_s < x[0] <= end_s]
    if not anchors or end_s-anchors[-1][0] > max_gap_s:
        return {'status': 'UNKNOWN_END_COVERAGE', 'mean_C': None, 'peak_C': None, 'end_C': None}
    area = 0.
    for index, (t, value) in enumerate(anchors):
        right = anchors[index+1][0] if index+1<len(anchors) else end_s
        a, b = max(start_s, t), min(end_s, right)
        if b>a:
            if right-t > max_gap_s:
                return {'status': 'UNKNOWN_INTERNAL_GAP', 'mean_C': None, 'peak_C': None, 'end_C': None}
            area += value*(b-a)
    return {'status': 'QUALIFIED_PAST_ZOH_WINDOW', 'window_s': [start_s, end_s],
            'mean_C': area/(end_s-start_s), 'peak_C': max(x[1] for x in anchors),
            'end_C': anchors[-1][1], 'max_gap_s': max_gap_s}


def saved_schedule_description(session):
    intervals = session.get('owner_intervals', [])
    overlap = 0.
    c = [x for x in intervals if x.get('task')=='C' and x.get('route')=='GPU']
    d = [x for x in intervals if x.get('task')=='D' and x.get('route')=='CPU']
    for a in c:
        for b in d:
            overlap += max(0., min(a['end_s'], b['end_s'])-max(a['start_s'], b['start_s']))
    if session.get('state_intervals') and not intervals:
        overlap = None
    return {'session_id': session['session_id'], 'cohort_id': session.get('cohort_id'),
            'source_family': session.get('source_family'), 'arm': session.get('arm'),
            'bank': session.get('bank'), 'owner_intervals': len(intervals),
            'actual_CG_DC_overlap_s': overlap,
            'requests': request_metrics(session.get('requests', [])),
            'AP35_180': ap_window(session.get('observations', [])),
            'observed_schedule': True, 'causal_policy_effect': False,
            'measured_J': None, 'energy_error_J': None, 'quality_verified': False}
