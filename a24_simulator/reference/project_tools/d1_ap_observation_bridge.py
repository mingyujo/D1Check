"""Opt-in PC observation boundary. No ADB, files, clocks or Android settings are invoked."""
from collections import deque
from dataclasses import dataclass
import math
import re
from threading import Lock
from tools import d1_logger_v4 as parser
from tools import d1_rolling_forecast as forecast

VERSION='host-ap-observation-boundary-v1'


@dataclass(frozen=True)
class ApObservation:
    session_id: str
    manifest_sha256: str
    host_clock_id: str
    before_ns: int
    after_ns: int
    host_received_mono: float
    ap_c: float
    thermal_status: int
    sensor_name: str='AP'
    sensor_type: int=0
    source: str='thermalservice_current_hal'
    unit: str='degC'
    receipt_evidence: str='producer_record_proxy'


def from_host_record(record,*,session_id,manifest_sha256,host_clock_id,received_host_mono=None):
    """Reuse an already returned thermal() result, with explicit owner identity."""
    raw=record['raw'];values=parser.parse_thermalservice(raw)
    block=re.search(r'Current temperatures from HAL:?\s*(.*?)(?:\n\s*(?:Current cooling devices|Temperature static thresholds|Temperature headroom thresholds)|\Z)',raw,re.S)
    named=re.findall(r'Temperature\{mValue\s*=\s*([^,}]+),\s*mType\s*=\s*(\d+),\s*mName\s*=\s*AP\s*[,}]',block.group(1)) if block else []
    if len(named)!=1 or named[0][1]!='0':
        raise ValueError('exact AP/type0 current HAL source required')
    ap=float(values['AP'])
    if ap!=float(named[0][0]) or ap!=float(record['AP']):raise ValueError('raw/parsed AP mismatch')
    producer=float(record['host_monotonic'])
    receipt=producer if received_host_mono is None else float(received_host_mono)
    if not math.isfinite(receipt) or receipt<producer:raise ValueError('consumer receipt precedes producer record')
    return ApObservation(session_id,manifest_sha256,host_clock_id,record['before_ns'],record['after_ns'],
                         receipt,ap,int(values['thermal_status']),receipt_evidence='producer_record_proxy' if received_host_mono is None else 'consumer_callback_timestamp')


class ObservationBuffer:
    def __init__(self,session_id,manifest_sha256,host_clock_id,capacity=32,max_age_ns=10_000_000_000):
        if not session_id or not host_clock_id or not re.fullmatch('[a-f0-9]{64}',manifest_sha256):
            raise ValueError('explicit observation owner required')
        if capacity!=32 or max_age_ns!=10_000_000_000:raise ValueError('fixed diagnostic bounds')
        self.owner=(session_id,manifest_sha256,host_clock_id);self.rows=deque(maxlen=capacity);self.lock=Lock()
        self.max_age_ns=max_age_ns

    def offer(self,row):
        if (row.session_id,row.manifest_sha256,row.host_clock_id)!=self.owner:raise ValueError('foreign observation owner/clock')
        if (row.sensor_name,row.sensor_type,row.source,row.unit)!=('AP',0,'thermalservice_current_hal','degC'):
            raise ValueError('numeric AP identity; status/headroom/BAT not substitutes')
        if row.receipt_evidence not in ('producer_record_proxy','consumer_callback_timestamp'):raise ValueError('receipt provenance')
        if (type(row.before_ns) is not int or type(row.after_ns) is not int or row.before_ns<0 or
            not row.before_ns<=row.after_ns or row.after_ns-row.before_ns>4_000_000_000 or
            not math.isfinite(row.ap_c) or not math.isfinite(row.host_received_mono) or row.host_received_mono<0 or
            type(row.thermal_status) is not int or not 0<=row.thermal_status<=6):
            raise ValueError('invalid observation value/bracket')
        with self.lock:
            if self.rows:
                previous=self.rows[-1]
                if row==previous:return 'duplicate_ignored'
                if row.after_ns<=previous.after_ns or row.host_received_mono<previous.host_received_mono:
                    return 'out_of_order_rejected'
            self.rows.append(row)
        return 'accepted'

    def at(self,*,device_decision_ns,host_now_mono,host_clock_id):
        # Integer Android and float PC clocks are checked separately, never subtracted.
        def unavailable(reason):return dict(status='unavailable',reason=reason,source=VERSION)
        if host_clock_id!=self.owner[2]:return unavailable('host_clock_scope_mismatch')
        if type(device_decision_ns) is not int:return unavailable('android_decision_clock_missing')
        if host_now_mono is None or not math.isfinite(host_now_mono):return unavailable('host_decision_clock_missing')
        with self.lock:rows=list(self.rows)
        eligible=[x for x in rows if x.after_ns<=device_decision_ns and x.host_received_mono<=host_now_mono]
        if not eligible:return unavailable('missing_or_future_delivery')
        row=eligible[-1]
        host_age=host_now_mono-row.host_received_mono
        device_age=device_decision_ns-row.before_ns
        if host_age>10 or device_age>self.max_age_ns:return unavailable('stale')
        if row.thermal_status!=0:return unavailable('thermal_environment_not_supported')
        return dict(status='available_host_diagnostic',sample=dict(t_ns=(row.before_ns+row.after_ns)//2,
                    after_ns=row.after_ns,ap_c=row.ap_c),host_age_s=host_age,device_age_s=device_age/1e9,
                    host_receipt_is_proxy=row.receipt_evidence=='producer_record_proxy',
                    android_app_received=False,hardware_sensor_refresh_known=False,source=VERSION)

    def app_status(self):
        return dict(status='unavailable',reason='no_verified_continuous_numeric_AP_delivery_to_current_APK')


def host_ap_forecast(case,frozen,buffer,*,origin_ns,device_decision_ns,host_now_mono,host_clock_id,times):
    observation=buffer.at(device_decision_ns=device_decision_ns,host_now_mono=host_now_mono,host_clock_id=host_clock_id)
    if observation['status']!='available_host_diagnostic':return dict(status='unavailable',observation=observation,prediction=None)
    if type(origin_ns) is not int or origin_ns<0:raise ValueError('Android common origin required')
    issue=(device_decision_ns-origin_ns)/1e9
    if issue<35 or any(p['hi']>issue for p in case['pre']):
        return dict(status='unavailable',reason='initial_conditions_not_yet_available',prediction=None)
    if not times or any(not math.isfinite(t) or not issue<=t<=issue+10 for t in times) or any(a>=b for a,b in zip(times,times[1:])):
        raise ValueError('fixed ordered ten-second horizon')
    sample=observation['sample'];t=(sample['t_ns']-origin_ns)/1e9
    if t<case['pre'][-1]['t']-1e-7:
        return dict(status='unavailable',reason='observation_before_frozen_anchor',prediction=None)
    # Already received sample is the only AP input at this boundary.
    baseline=float(forecast.frozen_ap(case,frozen,[t])[0])
    snapshot=dict(cutoff_s=issue,ap_status='available',ap_t=t,ap_value=sample['ap_c'],ap_delta=sample['ap_c']-baseline)
    pred=forecast.forecast_ap(case,frozen,snapshot,'ROLLING_OFFSET',times).tolist()
    return dict(status='calculated_host_diagnostic',prediction=pred,issue_s=issue,observation=observation,
                schedule_information='supplied future schedule conditional; not online policy validation',
                app_ready=False,accuracy_pass=None,strict_support=False,experiment_ready=False)
