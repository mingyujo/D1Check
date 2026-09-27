"""Device profile loader. Every leaf is {value, status, source}; value null -> masked (never replaced by 0)."""
from __future__ import annotations

import json
import os

import yaml

HERE = os.path.dirname(__file__)
RESOURCES = ('CPU4', 'GPU', 'NPU')


class Profile:
    def __init__(self, path=os.path.join(HERE, 'profiles', 'device_profile_S26.yaml')):
        self.path = path
        self.raw = yaml.safe_load(open(path, encoding='utf-8'))
        r = self.raw
        self.L0_ms = {res: r['latency_ms'][res]['median']['value'][100] for res in RESOURCES}
        self.P_load = {res: r['power_w']['load_d100'][res]['value'] for res in RESOURCES}
        self.P_idle = r['power_w']['idle']['value']
        self.t_start = r['throttle']['t_start_c']['value']
        self.init_s = {res: r['switch_cost_s'][f'idle->{res}']['value'] for res in RESOURCES}
        self.hal = r['limits']['hal_skin_thresholds_c']['value']
        gpu = r['throttle']['GPU']['params']['value']
        self.throttle_gpu = (json.load(open(os.path.join(os.path.dirname(path), gpu.split(':', 1)[1]), encoding='utf-8'))
                             if isinstance(gpu, str) and gpu.startswith('file:') else gpu)
        self.throttle_measured = {res: r['throttle'][res]['params']['value'] is not None for res in RESOURCES}
        self.tiers = {q: r['quality'][q]['value'] is not None for q in r['quality']}

    def status(self, *keys):
        node = self.raw
        for k in keys:
            node = node[k]
        return node['status']

    def supported(self, resource, tier='FP32'):
        """Mask: a (resource, tier) combination runs only if both latency and tier are present."""
        return self.L0_ms.get(resource) is not None and self.tiers.get(tier, False)

    def placeholders(self):
        out = []

        def walk(node, path):
            if isinstance(node, dict) and 'status' in node and 'value' in node:
                if node['status'] == 'placeholder':
                    out.append(('.'.join(path), node['value'], node['source']))
                return
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, path + [str(k)])
        walk(self.raw, [])
        return out
