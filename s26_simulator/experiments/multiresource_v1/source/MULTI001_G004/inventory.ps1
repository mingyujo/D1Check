param([int]$OwnerPid)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
while($null -ne ($request=[Console]::ReadLine())){
  try{
    $all=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|pypy|node|powershell|pwsh'} | Select-Object ProcessId,ParentProcessId,CreationDate,Name,CommandLine)
    $self=Get-CimInstance Win32_Process -Filter "ProcessId=$OwnerPid" | Select-Object ProcessId,ParentProcessId,CreationDate,Name,CommandLine
    @{all=$all;self=$self;utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -EscapeHandling EscapeNonAscii -Compress -Depth 5
  }catch{
    @{error=$_.Exception.Message} | ConvertTo-Json -EscapeHandling EscapeNonAscii -Compress
  }
}
