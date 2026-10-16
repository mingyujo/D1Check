SELECT start_ts,end_ts,(end_ts-start_ts)/1e9 AS trace_span_s FROM trace_bounds;
