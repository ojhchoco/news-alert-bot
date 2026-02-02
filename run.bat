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
uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause
