// D1Check opt-in observation only. No scheduling, retries or device access.
import 'dart:convert';
import 'package:logging/logging.dart';

class D1BaselineTrace {
  static const enabled = bool.fromEnvironment('D1_BASELINE_TRACE');
  static const maxEvents = 2048;
  static final _clock = Stopwatch()..start();
  static final _ids = Expando<int>('d1RunControl');
  static final _logger = Logger('D1BaselineTrace');
  static int _nextId = 0;
  static int _sequence = 0;
  static int dropped = 0;
  static int sinkFailures = 0;

  static void emit(Object control, String event, [String? detail]) {
    if (!enabled) return;
    try {
      if (_sequence >= maxEvents) {
        dropped++;
        if (dropped == 1) {
          _logger.info(jsonEncode({'schema': 'd1-ente-trace-v1',
            'event': 'overflow', 'sequence': _sequence + 1}));
        }
        return;
      }
      final id = _ids[control] ??= ++_nextId;
      _logger.info(jsonEncode({
        'schema': 'd1-ente-trace-v1',
        'control_id': id,
        'sequence': ++_sequence,
        'monotonic_us': _clock.elapsedMicroseconds,
        'event': event,
        'detail': detail,
      }));
    } catch (_) {
      // Observation must not replace the app's original failure/result.
      sinkFailures++;
    }
  }

  static T finish<T>(Object control, T disposition) {
    emit(control, 'run_return', disposition.toString());
    return disposition;
  }
}
