SELECT name, idx, severity, source, value FROM stats WHERE value > 0 AND
(severity IN ('error','data_loss') OR name GLOB '*lost*' OR name GLOB '*overrun*' OR name GLOB '*data_loss*');
