SELECT COUNT(*) AS sched_slices,COUNT(DISTINCT cpu) AS cpus,MIN(ts) AS first_ts_ns,MAX(ts+MAX(dur,0)) AS last_ts_ns,SUM(CASE WHEN dur<0 THEN 1 ELSE 0 END) AS open_slices FROM sched;
