@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python scripts\start_local.py
) else (
  py scripts\start_local.py
)
pause
