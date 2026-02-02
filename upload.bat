@echo off
chcp 65001 >nul
title Git 업로드 (Push)

cd /d "%~dp0"

if not exist ".git" (
    echo [안내] 이 폴더는 아직 Git 저장소가 아닙니다.
    echo PC와 노트북에서 사용하려면 먼저 한 번만 설정하세요:
    echo   1. GitHub 등에서 새 저장소 생성
    echo   2. 아래 명령 실행:
    echo      git init
    echo      git remote add origin https://github.com/사용자명/저장소명.git
    echo      git add .
    echo      git commit -m "초기 설정"
    echo      git branch -M main
    echo      git push -u origin main
    pause
    exit /b 1
)

echo [업로드] 변경사항을 커밋하고 원격 저장소로 푸시합니다...
echo.

git add -A
if errorlevel 1 (
    echo [오류] git add 실패
    pause
    exit /b 1
)

git status
echo.

set MSG=sync: %date% %time%
git commit -m "%MSG%" 2>nul
if errorlevel 1 (
    echo 변경사항이 없거나 이미 커밋되어 있습니다.
) else (
    echo 커밋 완료: %MSG%
)

git push
if errorlevel 1 (
    echo.
    echo [안내] push 실패 시 아래를 확인하세요:
    echo   - git remote -v 로 원격(origin) 설정 여부
    echo   - GitHub 로그인 또는 토큰 설정
    echo   - 최초 1회: git push -u origin main
    pause
    exit /b 1
)

echo.
echo [완료] 업로드가 끝났습니다. 노트북에서 download.bat 로 받으세요.
pause
