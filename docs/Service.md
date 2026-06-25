# PPT Generation Server - 서비스 관리

## 구성

| 항목 | 값 |
|------|-----|
| 서비스 이름 | `PPTGenServer` |
| 관리 도구 | NSSM (Non-Sucking Service Manager) |
| 실행 파일 | `C:\Users\wjdek\miniconda3\python.exe` |
| 포트 | `8010` |
| 로그 | `logs/service.log` |
| 시작 방식 | 부팅 시 자동 시작 (로그온 계정) |
| API 문서 | http://localhost:8010/docs |

---

## 최초 등록

관리자 PowerShell에서 실행:

> **주의:** PowerPoint COM 사용을 위해 반드시 **사용자 계정으로 실행**해야 합니다.  
> SYSTEM 계정으로 등록하면 `[WinError -2147024891] 액세스가 거부되었습니다` 오류가 발생합니다.

```powershell
nssm install PPTGenServer "C:\Users\wjdek\miniconda3\python.exe"
nssm set PPTGenServer AppParameters "-m uvicorn server.convert_server:app --host 0.0.0.0 --port 8010 --log-level info"
nssm set PPTGenServer AppDirectory "C:\dev\ppt-gen"
nssm set PPTGenServer AppStdout "C:\dev\ppt-gen\logs\service.log"
nssm set PPTGenServer AppStderr "C:\dev\ppt-gen\logs\service.log"
nssm set PPTGenServer AppStdoutCreationDisposition 4
nssm set PPTGenServer AppStderrCreationDisposition 4
nssm set PPTGenServer Start SERVICE_AUTO_START
Start-Service PPTGenServer
```

---

## 일상 관리 명령어

```powershell
# 시작
Start-Service PPTGenServer

# 중지
Stop-Service PPTGenServer

# 재시작
Restart-Service PPTGenServer

# 상태 확인
Get-Service PPTGenServer

# 로그 확인
Get-Content C:\dev\ppt-gen\logs\service.log -Tail 50
```

---

## 설정 변경 후 재시작

코드 변경은 재등록 없이 서버 재시작만 하면 됩니다.

```powershell
Restart-Service PPTGenServer
```

---

## 완전 제거

```powershell
Stop-Service PPTGenServer
nssm remove PPTGenServer confirm
```

---

## 문제 해결

### 서버가 시작되지 않을 때
```powershell
# 로그 확인
Get-Content C:\dev\ppt-gen\logs\service.log -Tail 100

# NSSM 서비스 상세 상태
nssm status PPTGenServer

# python 직접 실행해서 에러 확인
cd C:\dev\ppt-gen
C:\Users\wjdek\miniconda3\python.exe -m uvicorn server.convert_server:app --host 0.0.0.0 --port 8010
```

### 포트 충돌 확인
```powershell
netstat -ano | findstr :8010
```

### 서비스 마지막 상태 확인
```powershell
Get-Service PPTGenServer | Select-Object Status, StartType, DisplayName
```
