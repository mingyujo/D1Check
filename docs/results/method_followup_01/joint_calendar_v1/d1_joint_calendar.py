"""Offline calendar with both frozen-model peak and rectified AP-area caps.

Reuses the existing exact planner body in an isolated globals namespace. Only
the solver adapter adds epigraph variables; no old source/global mutation.
"""
import math
from types import FunctionType
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, OptimizeResult
from scipy.sparse import csr_matrix, eye, hstack, vstack
from tools import d1_deadline_calendar as original


def plan(frozen, initial, tickets, *, ap_cap_c, area_cap_c_s,
         scenario='mean', grid_s=.02, timeout_s=120.):
    if (not math.isfinite(ap_cap_c) or not math.isfinite(area_cap_c_s) or area_cap_c_s < 0):
        raise ValueError('explicit finite frozen-model comparison caps required')
    proof = dict(planning_area_cap_c_s=area_cap_c_s, area_cap_is_safety_criterion=False,
                 old_planner_mutated=False, added_epigraph_variables=146)
    query_count = 146
    ref = original.x.p.memory.initialize(initial['preload'], frozen['ap']['beta'], 30.)['reference_c']

    def solve(c, *, integrality, bounds, constraints, options):
        v = len(c); m = query_count
        matrix = csr_matrix(constraints.A)
        lower = np.broadcast_to(constraints.lb, (matrix.shape[0],)).copy()
        upper = np.broadcast_to(constraints.ub, (matrix.shape[0],)).copy()
        # The unchanged planner places its explicit peak constraints last.
        if matrix.shape[0] < m or not np.all(np.isneginf(lower[-m:])):
            raise ValueError('missing exact planner peak boundary')
        thermal = matrix[-m:]
        base = ap_cap_c-upper[-m:]
        weights = np.ones(m); weights[[0, -1]] = .5
        extended = vstack((
            hstack((matrix, csr_matrix((matrix.shape[0], m)))),
            hstack((thermal, -eye(m, format='csr'))),
            hstack((csr_matrix((1, v)), csr_matrix(weights[None, :]))),
        ), format='csr')
        lo = np.r_[lower, np.full(m+1, -np.inf)]
        hi = np.r_[upper, ref-base, area_cap_c_s]
        fit = original.milp(np.r_[c, np.zeros(m)],
            integrality=np.r_[integrality, np.zeros(m)],
            bounds=Bounds(np.r_[bounds.lb, np.zeros(m)], np.r_[bounds.ub, np.full(m, np.inf)]),
            constraints=LinearConstraint(extended, lo, hi), options=options)
        if fit.x is not None:
            vector = np.asarray(fit.x)
            lhs = extended@vector
            violation = float(max(np.max(np.maximum(0., lo-lhs)), np.max(np.maximum(0., lhs-hi))))
            if violation > 1e-5 or not np.all(np.isfinite(vector)):
                raise ValueError('joint calendar extended constraints violated')
            actual_planning_rise = np.maximum(0., base+thermal@vector[:v]-ref)
            proof.update(extended_max_numeric_violation=violation,
                         rounded_planning_AP_area_c_s=float(weights@actual_planning_rise),
                         planning_epigraph_area_c_s=float(weights@vector[v:]),
                         extended_variable_count=len(vector))
        # Old planner checks/replays original variables and original five phases.
        projected = OptimizeResult(dict(fit))
        if fit.x is not None: projected.x = np.asarray(fit.x)[:v]
        return projected

    isolated = FunctionType(original.plan.__code__, dict(original.plan.__globals__, milp=solve),
                            'joint_calendar_plan', original.plan.__defaults__)
    result = isolated(frozen, initial, tickets, scenario=scenario, grid_s=grid_s,
                      timeout_s=timeout_s, ap_cap_c=ap_cap_c)
    metric = result.get('metrics')
    proof['actual_replay_within_AP_area_cap'] = (None if metric is None else
        metric['thermal_degree_seconds'] is not None and metric['thermal_degree_seconds'] <= area_cap_c_s+1e-8)
    return dict(result, **proof)
