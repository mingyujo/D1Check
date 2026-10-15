SELECT name,idx,severity,source,value FROM stats WHERE value != 0 ORDER BY severity,name,idx;
