"""Synthetic boundary tests only. Authoring is not an execution permission.

No saved production data is read. Run only after the parent's source/test and
resource guard registration. No model fit or environment START is performed.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import m8_data as m


SID = '00000000-0000-5000-8000-000000000001'
ORIGIN = 1_000 * m.NS


def clock():
    return {'origin_source': 'UNIQUE_EVENTS_COMMON_START_ORIGIN_NS',
            'event_clock_field': 'mono_ns',
            'planned_clock_basis': 'COMMON_START_RELATIVE_NANOSECONDS',
            'planned_clock_shift_ns': 0, 'public_field_pointers': m.NATIVE_PUBLIC_POINTERS}


def public(count=1):
    return {'session_id': SID, 'concurrency': 'PAIR', 'arm': 'FIFO_GPU',
            'recipe': 'SYNTHETIC', 'route': 'C_GPU_D_CPU',
            'service_cutoff_ns': 120*m.NS, 'sensor_end_ns': 210*m.NS,
            'requests': [{'request_id': 'r' + str(i), 'ordinal': i, 'task': 'C',
                          'group': i, 'priority': 'urgent', 'scheduled_arrival_ns': 0,
                          'deadline_ns': 10*m.NS, 'input_sha256': 'a'*64,
                          'tensor_sha256': 'b'*64} for i in range(count)]}


def raw_request():
    q = {'request_id': 'r0', 'ordinal': 0, 'task': 'C', 'group': 0,
         'scheduled_arrival_ns': ORIGIN, 'deadline_ns': ORIGIN+10*m.NS,
         'backend': 'GPU', 'terminal_status': 'COMPLETED'}
    for index, key in enumerate(m.PHASES, 1):
        q[key] = ORIGIN + index * 10_000_000
    q['response_complete_ns'] = q['output_ready_ns']
    return q


def reference(archive='a.zip', sha='c'*64):
    return {'archive_path': archive, 'archive_sha256': 'd'*64, 'archive_bytes': 1,
            'member': 'raw/' + SID + '/requests.json', 'sha256': sha,
            'logical_stream': 'requests.json', 'source_generation': 'SYNTHETIC',
            'path_session_id': SID}


class M8BoundaryTests(unittest.TestCase):
    def planned(self, count=1):
        return m.project_public(public(count), SID, clock())

    def test_response_and_five_stage_conservation(self):
        row = m.normalize_requests([raw_request()], self.planned(), ORIGIN, public())[0]
        self.assertEqual(row['protocol'], 'CG_DC')
        self.assertEqual(row['response_s'], .05)
        self.assertEqual(row['available_s'], .08)
        self.assertEqual(len(row['phases_s']), 5)
        self.assertAlmostEqual(sum(row['phases_s'].values()), row['available_s']-row['dispatch_s'])
        self.assertFalse(row['actual_hardware_delegate_verified'])

    def test_duplicate_and_unplanned_request_fail(self):
        q = raw_request()
        with self.assertRaisesRegex(ValueError, 'Duplicate observed'):
            m.normalize_requests([q, q], self.planned(), ORIGIN, public())
        q = dict(q, request_id='unplanned')
        with self.assertRaisesRegex(ValueError, 'Unplanned observed'):
            m.normalize_requests([q], self.planned(), ORIGIN, public())

    def test_native_integer_group_is_not_coerced(self):
        q = raw_request(); q['group'] = '0'
        row = m.normalize_requests([q], self.planned(), ORIGIN, public())[0]
        self.assertIn('PLAN_BINDING_MISMATCH_group', row['issues'])
        self.assertIsNone(row['response_s'])
        self.assertEqual(row['group'], 0)
        self.assertEqual(row['public_native_group_type'], 'int')
        p = public(); p['requests'][0]['group'] = False
        with self.assertRaisesRegex(ValueError, 'native type'):
            m.project_public(p, SID, clock())

    def test_missing_32_kept_in_planned_denominator(self):
        rows = m.normalize_requests([], self.planned(32), ORIGIN, public(32))
        d = m.denominators(rows)['ALL']
        self.assertEqual((d['planned'], d['responded'], d['missing_records'], d['no_valid_response']), (32, 0, 32, 32))
        self.assertTrue(all(q['available_s'] is None for q in rows))

    def test_failed_unclosed_owner_not_zero_activity(self):
        q = raw_request(); q['terminal_status'] = 'FAILED'
        for key in ('output_ready_ns', 'persist_complete_ns', 'worker_release_ns', 'lane_available_ns', 'response_complete_ns'):
            q.pop(key, None)
        rows = m.normalize_requests([q], self.planned(), ORIGIN, public())
        intervals, report = m.ownership(rows)
        self.assertEqual(intervals, [])
        self.assertEqual(len(report['unclosed_owners']), 1)
        self.assertEqual(m.denominators(rows)['ALL']['failed'], 1)

    def test_request_event_coverage_needs_exact_unique_phase_events(self):
        q = raw_request()
        rows = m.normalize_requests([q], self.planned(), ORIGIN, public())
        events = [(i, {'kind': kind, 'request_id': 'r0', field: q[field]}, 'synthetic')
                  for i, (kind, field) in enumerate((('queue_entry', 'queue_entry_ns'),
                                                     ('dispatch', 'dispatch_ns'),
                                                     ('lane_available', 'lane_available_ns')))]
        self.assertEqual(m.request_event_coverage(rows, events, ORIGIN)['status'], 'COMPLETE')
        self.assertEqual(m.request_event_coverage(rows, events + [events[0]], ORIGIN)['status'], 'UNKNOWN')
        wait = (9, {'kind': 'wait_start', 'wait_id': 'w'}, 'synthetic')
        self.assertEqual(m.request_event_coverage(rows, events + [wait], ORIGIN)['status'], 'UNKNOWN')

    def test_idle_denominator_and_unknown_initial(self):
        self.assertEqual(m.normalize_requests([], self.planned(0), ORIGIN, public(0)), [])
        self.assertEqual(m.denominators([])['ALL']['planned'], 0)
        ap = m.ap_zoh([], None)
        self.assertFalse(ap['qualified'])
        self.assertIsNone(ap['mean_c'])

    def test_clock_never_inferred_from_arrivals_or_later_events(self):
        origin, issues = m.resolve_origin([], {}, clock())
        self.assertIsNone(origin)
        self.assertTrue(issues)
        rows = [(1, {'kind': 'common_start', 'origin_ns': ORIGIN}, 'x')]
        origin, issues = m.resolve_origin(rows, {'common_start_ns': ORIGIN+1}, clock())
        self.assertIsNone(origin)
        self.assertIn('EVENT_SUMMARY_ORIGIN_CONFLICT', issues)
        contract = dict(clock(), origin_source='SUMMARY_COMMON_START_NS')
        origin, issues = m.resolve_origin([], {'common_start_ns': ORIGIN}, contract)
        self.assertEqual(origin, ORIGIN)

    def test_empirical_clock_still_checks_every_observed_request_clock(self):
        q = raw_request(); q['scheduled_arrival_ns'] += 1
        rows = m.normalize_requests([q], self.planned(), ORIGIN, public())
        self.assertIn('PLAN_BINDING_MISMATCH_scheduled_arrival_ns', rows[0]['issues'])
        self.assertIsNone(rows[0]['response_s'])
        q = raw_request(); q['deadline_ns'] += 1
        rows = m.normalize_requests([q], self.planned(), ORIGIN, public())
        self.assertIn('PLAN_BINDING_MISMATCH_deadline_ns', rows[0]['issues'])
        self.assertFalse(rows[0]['complete_vector'])
        # Missing rows stay missing; no shifted origin repairs them.
        rows = m.normalize_requests([], self.planned(), None, public())
        self.assertIsNone(rows[0]['response_s'])

    def test_hal_channel_bracket_and_sensor_timestamp_preserved(self):
        good = {'device_elapsed_before_ns': ORIGIN-2*m.NS, 'device_elapsed_after_ns': ORIGIN-m.NS,
                'sensor_source_section': 'CURRENT_HAL',
                'sensors': [{'sensor_name': 'AP', 'sensor_type': 0, 'value_c': 31.5,
                             'sensor_timestamp_ns': 123, 'cache_age_ns': 456, 'path': '/synthetic/AP'},
                            {'sensor_name': 'SKIN', 'sensor_type': 3, 'value_c': 29}]}
        bad = copy.deepcopy(good); bad['device_elapsed_after_ns'] = ORIGIN-3*m.NS
        text = (json.dumps(good)+'\n'+json.dumps(bad)).encode()
        points, channels, invalid = m.parse_hal(text, ORIGIN, {'member': 'synthetic'})
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['t_s'], -1)
        self.assertEqual(points[0]['sensor_timestamp_ns'], 123)
        self.assertEqual(points[0]['sensor_path'], '/synthetic/AP')
        self.assertEqual(len(channels), 2)
        self.assertEqual(len(invalid), 1)

    def test_5s_primary_and_10s_diagnostic_are_separate(self):
        times = [30, 35, 41] + list(range(45, 186, 5))
        pts = [{'t_ns': t*m.NS, 'ap_c': 30.0} for t in times]
        self.assertFalse(m.ap_zoh(pts, 30, 5)['qualified'])
        self.assertTrue(m.ap_zoh(pts, 30, 10)['qualified'])

    def test_zoh_uses_left_value_not_future_interpolation(self):
        pts = [{'t_ns': t*m.NS, 'ap_c': 10 if t == 35 else 20} for t in range(30, 186, 5)]
        report = m.ap_zoh(pts, 15, 5)
        self.assertTrue(report['qualified'])
        self.assertAlmostEqual(report['mean_c'], (10*5+20*140)/145)
        dup = pts+[pts[2]]
        self.assertFalse(m.ap_zoh(dup, 15, 5)['qualified'])

    def test_repack_dedup_retains_all_sources_conflict_fails(self):
        a, b = reference('a.zip'), reference('b.zip')
        rows = m.deduplicate_refs([a, b])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['all_republications']), 2)
        with self.assertRaisesRegex(ValueError, 'CONFLICTING_LOGICAL'):
            m.deduplicate_refs([a, reference('c.zip', 'e'*64)])

    def test_metadata_builder_excludes_unbound_clocks_and_conflicts(self):
        a = reference(); a['role'] = 'RAW_STREAM'
        pub = dict(a, member='public_manifests/'+SID+'.json', logical_stream='public_manifest')
        inventory = {'members': [a, pub], 'archives': []}
        roster = {SID: {'session_id': SID, 'family': 'SYNTHETIC', 'block': 'B', 'stage': 'CONFIRM'}}
        plan = m.build_session_specs(inventory, roster, {})
        self.assertEqual(plan['sessions'][0]['use'], 'INVENTORY_EXCLUDED')
        self.assertIn('CLOCK', plan['sessions'][0]['exclusion'])
        self.assertEqual(plan['describe']['raw_payload_reads'], 0)

    def test_phase_b_metadata_binding_list_preserves_family_aliases(self):
        rows = [{'payload_session_id': SID, 'public_sha256': 'a'*64,
                 'metadata_bindings': [{'literal_family': 'SOURCE_FAMILY'}, {'literal_family': 'REPACK_ALIAS'}],
                 'clock': {'status': 'UNKNOWN_CATALOG_CODE_CLOCK_CHAIN'}}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'synthetic_metadata.json'
            raw = json.dumps(rows).encode(); path.write_bytes(raw)
            pin = {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            roster = m.roster_from_metadata([{'kind': 'FINAL_PHASE_B_OCCURRENCES', 'pin': pin}])
        self.assertEqual(roster[SID]['family_aliases'], ['SOURCE_FAMILY', 'REPACK_ALIAS'])
        self.assertEqual(roster[SID]['family'], 'SOURCE_FAMILY')
        self.assertEqual(len(roster[SID]['metadata_conflicts']), 1)
        self.assertEqual(len(roster[SID]['metadata_occurrences']), 2)

    def test_public_payload_session_binding_is_required(self):
        p = public(); p['session_id'] = 'different'
        with self.assertRaisesRegex(ValueError, 'session binding'):
            m.project_public(p, SID, clock())

    def test_raw_access_gate_rejects_unregistered_operation(self):
        with self.assertRaisesRegex(ValueError, 'registered raw'):
            m.validate_operation({'schema': m.OP_SCHEMA, 'allow_raw_access': False}, {'members': []})

    def test_selected_member_read_and_sha_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'synthetic.zip'
            member = 'raw/'+SID+'/requests.json'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr(member, b'[]')
                z.writestr('UNSELECTED.txt', b'must not be decompressed')
            ref = reference(str(path), hashlib.sha256(b'[]').hexdigest())
            ref.update(archive_sha256=m.file_sha(path), archive_bytes=path.stat().st_size)
            original = zipfile.ZipFile.read; names = []
            def tracked(handle, name, *args, **kwargs):
                names.append(name)
                return original(handle, name, *args, **kwargs)
            with mock.patch.object(zipfile.ZipFile, 'read', tracked):
                data, receipts = m._read_selected([ref])
            self.assertEqual(names, [member])
            self.assertEqual(data[m.member_key(ref)], b'[]')
            self.assertFalse(receipts[m.member_key(ref)]['unselected_members_decompressed'])
            ref['sha256'] = 'f'*64
            with self.assertRaisesRegex(ValueError, 'SHA differs'):
                m._read_selected([ref])


if __name__ == '__main__':
    unittest.main()
