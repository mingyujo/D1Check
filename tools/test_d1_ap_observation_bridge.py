import copy
from dataclasses import replace
import unittest
from tools import d1_ap_observation_bridge as b

HASH='a'*64
RAW='''Thermal Status: 0
Cached temperatures:
Temperature{mValue=99.0, mType=0, mName=AP, mStatus=0}
Current temperatures from HAL:
Temperature{mValue=30.0, mType=0, mName=AP, mStatus=0}
Temperature{mValue=29.0, mType=2, mName=BAT, mStatus=0}
Current cooling devices from HAL:
'''


class ObservationBridgeTests(unittest.TestCase):
    def sample(self,**changes):
        return replace(b.ApObservation('session',HASH,'host-scope',1_000_000_000,1_300_000_000,10.,30.,0),**changes)

    def receiver(self):return b.ObservationBuffer('session',HASH,'host-scope')

    def test_real_parser_excludes_cached_and_wrong_sensor(self):
        record=dict(raw=RAW,AP='30.0',before_ns=1_000_000_000,after_ns=1_300_000_000,host_monotonic=10.)
        row=b.from_host_record(record,session_id='session',manifest_sha256=HASH,host_clock_id='host-scope')
        self.assertEqual(row.ap_c,30.)
        bad=dict(record,raw=RAW.replace('Current temperatures from HAL:','No current HAL:'))
        with self.assertRaises(ValueError):b.from_host_record(bad,session_id='session',manifest_sha256=HASH,host_clock_id='host-scope')
        bad=dict(record,raw=RAW.replace('mType=0, mName=AP','mType=2, mName=AP'))
        with self.assertRaises(ValueError):b.from_host_record(bad,session_id='session',manifest_sha256=HASH,host_clock_id='host-scope')
        bad=dict(record,raw=RAW.replace('Current cooling devices from HAL:','Temperature{mValue=31.0, mType=0, mName=AP, mStatus=0}\nCurrent cooling devices from HAL:'))
        with self.assertRaises(ValueError):b.from_host_record(bad,session_id='session',manifest_sha256=HASH,host_clock_id='host-scope')

    def test_owner_unit_clock_and_nonfinite_rejected(self):
        receiver=self.receiver()
        for field,value in [('session_id','other'),('manifest_sha256','b'*64),('host_clock_id','other'),('unit','headroom'),('sensor_name','BAT'),('ap_c',float('nan'))]:
            with self.assertRaises(ValueError):receiver.offer(self.sample(**{field:value}))

    def test_separate_clocks_future_stale_and_missing(self):
        receiver=self.receiver();receiver.offer(self.sample())
        self.assertEqual(receiver.at(device_decision_ns=None,host_now_mono=10.,host_clock_id='host-scope')['reason'],'android_decision_clock_missing')
        self.assertEqual(receiver.at(device_decision_ns=1_200_000_000,host_now_mono=10.,host_clock_id='host-scope')['status'],'unavailable')
        self.assertEqual(receiver.at(device_decision_ns=1_400_000_000,host_now_mono=9.,host_clock_id='host-scope')['status'],'unavailable')
        self.assertEqual(receiver.at(device_decision_ns=1_400_000_000,host_now_mono=21.,host_clock_id='host-scope')['reason'],'stale')
        self.assertEqual(receiver.at(device_decision_ns=11_100_000_000,host_now_mono=10.,host_clock_id='host-scope')['reason'],'stale')
        self.assertEqual(receiver.at(device_decision_ns=1_400_000_000,host_now_mono=10.,host_clock_id='other')['status'],'unavailable')

    def test_duplicate_and_older_observation_do_not_replace(self):
        receiver=self.receiver();row=self.sample();self.assertEqual(receiver.offer(row),'accepted')
        self.assertEqual(receiver.offer(row),'duplicate_ignored')
        self.assertEqual(receiver.offer(self.sample(before_ns=900_000_000,after_ns=1_200_000_000,host_received_mono=11.)),'out_of_order_rejected')
        self.assertEqual(len(receiver.rows),1)
        self.assertEqual(receiver.app_status()['status'],'unavailable')

    def test_thermal_gate_and_bounded_buffer(self):
        receiver=self.receiver();receiver.offer(self.sample(thermal_status=2))
        self.assertEqual(receiver.at(device_decision_ns=1_400_000_000,host_now_mono=10.,host_clock_id='host-scope')['status'],'unavailable')
        receiver=self.receiver()
        for i in range(80):receiver.offer(self.sample(before_ns=(i+1)*1_000_000_000,after_ns=(i+1)*1_000_000_000+10_000_000,host_received_mono=float(i+10)))
        self.assertEqual(len(receiver.rows),32)

    def test_forecast_boundary_and_no_device_execution(self):
        r=b.forecast;case=r.h.m.read(r.BUNDLE/'inputs.json.gz')[1];frozen=r.h.m.read(r.h.m.MODEL)
        origin=100_000_000_000;point=case['pre'][-1]
        row=self.sample(before_ns=origin+round(point['lo']*1e9),after_ns=origin+round(point['hi']*1e9),ap_c=point['ap'])
        receiver=self.receiver();receiver.offer(row)
        result=b.host_ap_forecast(case,frozen,receiver,origin_ns=origin,device_decision_ns=origin+35_000_000_000,host_now_mono=10.,host_clock_id='host-scope',times=[36.,40.,45.])
        self.assertEqual(result['status'],'calculated_host_diagnostic');self.assertFalse(result['app_ready'])
        with self.assertRaises(ValueError):b.host_ap_forecast(case,frozen,receiver,origin_ns=origin,device_decision_ns=origin+35_000_000_000,host_now_mono=10.,host_clock_id='host-scope',times=[46.])
        self.assertEqual(r.h.m.sha(r.h.m.MODEL),r.h.m.MODEL_SHA)

    def test_initial_conditions_not_available_and_horizon_order(self):
        r=b.forecast;case=r.h.m.read(r.BUNDLE/'inputs.json.gz')[1];frozen=r.h.m.read(r.h.m.MODEL)
        origin=100_000_000_000;point=case['pre'][-1];receiver=self.receiver()
        receiver.offer(self.sample(before_ns=origin+round(point['lo']*1e9),after_ns=origin+round(point['hi']*1e9),ap_c=point['ap']))
        answer=b.host_ap_forecast(case,frozen,receiver,origin_ns=origin,device_decision_ns=origin+34_000_000_000,host_now_mono=10.,host_clock_id='host-scope',times=[35.])
        self.assertEqual(answer['status'],'unavailable')
        with self.assertRaises(ValueError):b.host_ap_forecast(case,frozen,receiver,origin_ns=origin,device_decision_ns=origin+35_000_000_000,host_now_mono=10.,host_clock_id='host-scope',times=[40.,36.])

    def test_producer_stamp_is_not_consumer_receipt(self):
        record=dict(raw=RAW,AP='30.0',before_ns=1_000_000_000,after_ns=1_300_000_000,host_monotonic=10.)
        proxy=b.from_host_record(record,session_id='session',manifest_sha256=HASH,host_clock_id='host-scope')
        self.assertEqual(proxy.receipt_evidence,'producer_record_proxy')
        actual=b.from_host_record(record,session_id='session',manifest_sha256=HASH,host_clock_id='host-scope',received_host_mono=12.)
        receiver=self.receiver();receiver.offer(actual)
        self.assertEqual(receiver.at(device_decision_ns=1_400_000_000,host_now_mono=11.,host_clock_id='host-scope')['status'],'unavailable')
        ready=receiver.at(device_decision_ns=1_400_000_000,host_now_mono=12.,host_clock_id='host-scope')
        self.assertFalse(ready['host_receipt_is_proxy'])
        with self.assertRaises(ValueError):b.from_host_record(record,session_id='session',manifest_sha256=HASH,host_clock_id='host-scope',received_host_mono=9.)


if __name__=='__main__':unittest.main()
