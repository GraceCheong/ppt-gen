@echo off
setlocal

cd /d C:\dev\ppt-gen

if not exist logs mkdir logs

call C:\Users\wjdek\miniconda3\Scripts\activate.bat base
if errorlevel 1 (
  exit /b 1
)

python -m uvicorn server.convert_server:app --host 0.0.0.0 --port 8010 --log-level info

endlocal
