SELECT name,idx,severity,source,value FROM stats WHERE name GLOB 'ftrace*' ORDER BY name,idx;
