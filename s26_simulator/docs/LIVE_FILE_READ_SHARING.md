# Windows 실시간 원장 읽기 규약

2026-10-17 06:29 KST G004는 다음 건 START를 append하기 위해 원장을 여는 순간 PermissionError13으로 중단됐다. 저장된2,711건은 모두 종결됐고 다음 건은 설정 파일만 있었다. 다른 작업의 등록 시점 원장 읽기와 시간상 겹쳤다는 이력도 있다. 단독 원인까지 입증한 것은 아니다.

진행 중인 원장·로그에는 PowerShell `Get-Content`나 기본 `File.ReadLines`처럼 쓰기 공유를 보장하지 않는 읽기를 쓰지 않는다. 불변 progress snapshot·종료 파일을 우선한다. 반드시 실시간 읽기가 필요하면 아래처럼 쓰기 공유를 허용하고 즉시 닫는다.

```powershell
function Read-LiveText([string]$Path) {
    $share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::Open,
        [IO.FileAccess]::Read, $share)
    $reader = [IO.StreamReader]::new($stream, [Text.Encoding]::UTF8, $true)
    try { $reader.ReadToEnd() } finally { $reader.Dispose() }
}
```

읽기 공유 허용은 부분 행을 완전한 START로 간주해도 된다는 뜻이 아니다. 실제 종결·행 수·SHA 감사는 생산 작업자 종료와 공유 mutex 획득 뒤 한다. 실패 후에는 원 raw/prepared/원장·완료·미시작 설정부터 대조한다. 이미 소비된 미저장 identity를 재시뮬레이션하지 않는다.

이 중단의 복구는 새 운영 등록에서 완결된 저장 prefix를 검산하고 **미시작** EVAL만 실행한다. 동결 정책/물리/기한/DEV선정/기존 결과를 바꾸지 않는다. 원 실패 기록은 남긴다. 공유 슬롯과 다른 작업 예약을 우회하거나 임의로 작업자를 재시작하지 않는다.
