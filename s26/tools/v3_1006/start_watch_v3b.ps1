# V3 v2 (P1h 1007): start the host watchers exactly as P1g did (scripts unchanged), new CSV names *_v3b ("감시 켬" 이어 씀).
#   SKIN watch  = s26\tools\s26_skin_watch_npu.py <serial> skin_watch_v3b.csv skin_watch.stop (15 s; SKIN >= 45 -> force-stop runner)
#   call/screen = s26\tools\night_1005e\phone_watch_1005e.ps1 -OutCsv phone_watch_v3b.csv -StopFile phone_watch.stop (10 s, read-only)
# Serial only from $env:ANDROID_SERIAL (process argument, never written to a file). PIDs -> host_pids_v3b.txt.
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_host_v3_1007"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER) { throw "ANDROID_SERIAL not set" }
foreach ($stopName in @("phone_watch.stop", "skin_watch.stop")) { if (Test-Path "$H\$stopName") { Remove-Item "$H\$stopName" } }
$ps = Start-Process -FilePath "py" -ArgumentList @("-X", "utf8", "$wd\s26\tools\s26_skin_watch_npu.py", "`"$DEVSER`"", "$H\skin_watch_v3b.csv", "$H\skin_watch.stop") -WindowStyle Hidden -PassThru
$pp = Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$wd\s26\tools\night_1005e\phone_watch_1005e.ps1", "-OutCsv", "$H\phone_watch_v3b.csv", "-StopFile", "$H\phone_watch.stop") -WindowStyle Hidden -PassThru
$line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] skin=$($ps.Id) phone=$($pp.Id)"
Add-Content -Encoding UTF8 "$H\host_pids_v3b.txt" $line
$line