SELECT name,COUNT(*) AS events FROM ftrace_event GROUP BY name ORDER BY name;
