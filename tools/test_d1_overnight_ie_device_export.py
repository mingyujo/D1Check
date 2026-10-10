import gzip,json,unittest
from tools import d1_overnight_ie_run as d


class CommonClock(unittest.TestCase):
    def test_original_native_trace_and_both_payload_origins_are_exactly_same(self):
        folder=d.LOCAL/'device_common0'
        if not folder.exists():self.skipTest('local completed representative archives required')
        receipt=d.read(folder/'contract.json')
        for role in d.ROLES:
            raw=json.loads(gzip.decompress((d.LOCAL/'items'/f'representative_{role}.json.gz').read_bytes()))
            relative=d.read(d.LOCAL/f'device_plan_{role}.json');common=d.read(folder/f'device_plan_{role}.json')
            self.assertEqual(d.sha(folder/f'device_plan_{role}.json'),receipt['payloads'][role]['sha256'])
            self.assertEqual(len(common['requests']),96);self.assertEqual(common['pc_metrics'],raw['row'])
            ledger={q['ordinal']:q for q in raw['result']['ledger']}
            for a,b in zip(relative['requests'],common['requests']):
                q=ledger[b['ordinal']]
                self.assertEqual(b['offset_ms'],35_000+b['ordinal']*350)
                self.assertEqual(b['offset_ms'],a['offset_ms']+35_000)
                self.assertEqual(b['release_offset_ns'],a['release_offset_ns']+35_000_000_000)
                self.assertEqual(b['release_offset_ns'],q['dispatch_ns'])
                self.assertEqual(b['pc_lane_available_ns'],q['lane_available_ns'])
                self.assertGreaterEqual(q['dispatch_ns'],q['arrival_ns'])
                self.assertEqual(q['arrival_ns'],35_000_000_000+b['ordinal']*350_000_000)
    def test_native_arrivals_follow_last_preload_observation(self):
        source=d.LOCAL/'inputs.json' if (d.LOCAL/'inputs.json').exists() else d.PUBLIC/'cases.json'
        inputs=d.read(source);f,initial,_=d.x.r.h.load()
        end=max(q['hi'] for q in initial['initial']['preload'])
        self.assertLess(end,35.)
        self.assertGreater(min(q['arrival_ns']/1e9 for q in inputs['representative']['tickets']),end)

if __name__=='__main__':unittest.main()
