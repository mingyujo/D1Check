// PC-only harness. Copy beside the instrumented original MlRunControl.
import 'dart:convert';
import 'package:logging/logging.dart';
import 'package:photos/services/machine_learning/ml_run_control.dart';
import 'package:photos/services/machine_learning/d1_baseline_trace.dart';

void check(bool condition, String message) {
  if (!condition) throw StateError(message);
}

void main() {
  final records = <Map<String, dynamic>>[];
  Logger.root.level = Level.ALL;
  final subscription = Logger.root.onRecord.listen((record) {
    if (record.loggerName == 'D1BaselineTrace') {
      records.add(jsonDecode(record.message) as Map<String, dynamic>);
    }
  });
  final control = MlRunControl();
  var calls = 0;
  control.attachOnStop(() => calls++);
  control.requestStop(MlStopReason.controller);
  control.requestStop(MlStopReason.manual);
  check(calls == 1 && control.stopReason == MlStopReason.controller,
      'first stop reason and callback must remain latched');
  control.attachOnStop(() => calls++);
  check(calls == 2, 'late attachment preserves original immediate callback');
  final failing = MlRunControl();
  final original = StateError('original callback error');
  failing.attachOnStop(() => throw original);
  Object? caught;
  try { failing.requestStop(MlStopReason.manual); } catch (e) { caught = e; }
  check(identical(caught, original) && failing.stopRequested,
      'trace must not hide original callback failure');
  final value = Object();
  check(identical(D1BaselineTrace.finish(control, value), value),
      'finish must return the exact original result');
  if (D1BaselineTrace.enabled) {
    check(records.where((e) => e['event'] == 'stop_latched').length == 2,
        'duplicate stop must not generate a new latch');
    final times = records.map((e) => e['monotonic_us'] as int).toList();
    for (var i = 1; i < times.length; i++) {
      check(times[i] >= times[i - 1], 'monotonic ordering');
    }
    for (var i = 0; i < D1BaselineTrace.maxEvents + 2; i++) {
      D1BaselineTrace.emit(control, 'fixture');
    }
    check(records.length == D1BaselineTrace.maxEvents + 1,
        'bounded events plus exactly one overflow marker');
    check(records.last['event'] == 'overflow' && D1BaselineTrace.dropped > 0,
        'loss must be marked');
  } else {
    check(records.isEmpty, 'disabled tracing must emit nothing');
  }
  subscription.cancel();
  print(jsonEncode({'passed': true, 'trace_enabled': D1BaselineTrace.enabled,
    'boundary': 'original MlRunControl only; MLService/Flutter not executed',
    'device_commands': 0}));
}
