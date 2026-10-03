SELECT name, value FROM stats WHERE value > 0 AND
(severity='error' OR name GLOB '*lost*' OR name GLOB '*overrun*' OR name GLOB '*data_loss*');
