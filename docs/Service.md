# PPT Generation Server - 서비스 관리

## 구성

| 항목 | 값 |
|------|-----|
| Task 이름 | `PPTGenServer` |
| 실행 파일 | `tools/server/run-server.bat` |
| 포트 | `8010` |
| 로그 | `logs/service.log` |
| 시작 방식 | 부팅 시 자동 시작 (SYSTEM 계정) |
| API 문서 | http://localhost:8010/docs |

---

## 최초 등록

관리자 PowerShell에서 실행:

> **주의:** PowerPoint COM 사용을 위해 반드시 **사용자 계정(`daeun\daeun`)** 으로 등록해야 합니다.  
> SYSTEM 계정으로 등록하면 `[WinError -2147024891] 액세스가 거부되었습니다` 오류가 발생합니다.

```powershell
$action   = New-ScheduledTaskAction -Execute "C:\Windows\System32\cmd.exe" `
                -Argument "/c C:\dev\ppt-gen\tools\server\run-server.bat" `
                -WorkingDirectory "C:\dev\ppt-gen"
$trigger  = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName "PPTGenServer" `
    -Action $action -Trigger $trigger -Settings $settings `
    -RunLevel Highest `
    -User "daeun\daeun" `
    -Password (Read-Host "Password") `
    -Force
```

---

## 일상 관리 명령어

```powershell
# 시작
Start-ScheduledTask -TaskName "PPTGenServer"

# 중지
Stop-ScheduledTask -TaskName "PPTGenServer"

# 상태 확인
Get-ScheduledTask -TaskName "PPTGenServer"

# 로그 확인
Get-Content C:\dev\ppt-gen\logs\service.log -Tail 50
```

---

## 설정 변경 후 재등록

코드 변경은 재등록 없이 서버 재시작만 하면 됩니다.  
배치 파일(`run-server.bat`) 내용을 바꾼 경우에는 재등록이 필요합니다.

```powershell
# 중지 후 재등록
Stop-ScheduledTask -TaskName "PPTGenServer"
Unregister-ScheduledTask -TaskName "PPTGenServer" -Confirm:$false
# 위의 "최초 등록" 명령어 다시 실행
```

---

## 완전 제거

```powershell
Stop-ScheduledTask -TaskName "PPTGenServer"
Unregister-ScheduledTask -TaskName "PPTGenServer" -Confirm:$false
```

---

## 문제 해결

### 서버가 시작되지 않을 때
```powershell
# 로그 확인
Get-Content C:\dev\ppt-gen\logs\service.log -Tail 100

# 배치 파일 직접 실행해서 에러 확인
C:\dev\ppt-gen\tools\server\run-server.bat
```

### 포트 충돌 확인
```powershell
netstat -ano | findstr :8010
```

### Task Scheduler 마지막 실행 결과 확인
```powershell
Get-ScheduledTaskInfo -TaskName "PPTGenServer" | Select-Object LastRunTime, LastTaskResult
```
> `LastTaskResult`가 `0`이면 정상, 그 외는 실패 코드

### conda 환경 문제
`run-server.bat` 안의 conda 경로 및 환경 이름을 확인하세요:
```bat
call C:\Users\daeun\miniconda3\Scripts\activate.bat base
```
