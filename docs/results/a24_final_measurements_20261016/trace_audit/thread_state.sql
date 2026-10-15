SELECT state,COUNT(*) AS state_slices FROM thread_state GROUP BY state ORDER BY state;
