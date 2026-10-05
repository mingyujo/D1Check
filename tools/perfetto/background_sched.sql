SELECT s.ts, s.dur, s.cpu,
CASE WHEN p.name = 'com.example.d1check.benchmarkrunner.modelprobe:model_probe' THEN 'benchmark'
 WHEN p.name GLOB '*traced*' OR p.name GLOB '*perfetto*' THEN 'tracer'
 WHEN t.tid = 0 THEN 'idle'
 WHEN p.name IS NULL THEN 'unknown' ELSE 'other' END AS activity_class
FROM sched_slice s LEFT JOIN thread t USING(utid) LEFT JOIN process p USING(upid)
WHERE s.dur > 0 ORDER BY s.ts;
