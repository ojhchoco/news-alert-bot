@echo off
chcp 65001 >nul
title Git 다운로드 (Pull)

cd /d "%~dp0"

if not exist ".git" (
    echo [안내] 이 폴더는 아직 Git 저장소가 아닙니다.
    echo PC에서 이미 저장소를 만들었다면, 노트북에서는 아래처럼 클론하세요:
    echo   git clone https://github.com/사용자명/저장소명.git
    echo   cd 저장소폴더명
    echo.
    echo 그 다음 가상환경 설정:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

echo [다운로드] 원격 저장소에서 최신 내용을 가져옵니다...
echo.

git pull
if errorlevel 1 (
    echo.
    echo [오류] pull 실패. 충돌(conflict)이 있으면 파일을 수정한 뒤 다시 실행하세요.
    pause
    exit /b 1
)

echo.
echo [완료] 다운로드가 끝났습니다.
pause
