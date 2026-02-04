@echo off
chcp 65001 >nul
title News Alert Bot

cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo [오류] 가상환경이 없습니다. 먼저 다음을 실행하세요:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo.
echo [안내] 서버가 켜지면 브라우저에서 http://localhost:8000 이 자동으로 열립니다.
echo         안 열리면 직접 주소창에 입력하세요.
echo.
start http://localhost:8000
uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause
