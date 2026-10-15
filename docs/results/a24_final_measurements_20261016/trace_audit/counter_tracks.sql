SELECT ct.name,COUNT(*) AS samples,MIN(c.ts) AS first_ts_ns,MAX(c.ts) AS last_ts_ns FROM counter c JOIN counter_track ct ON ct.id=c.track_id GROUP BY ct.name ORDER BY ct.name;
