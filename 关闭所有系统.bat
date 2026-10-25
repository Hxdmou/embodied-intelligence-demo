@echo off
title 关闭所有系统（便携版）
cls

echo.
echo ==============================
echo    关闭所有系统
echo ==============================
echo.
echo 正在停止所有 Python / Streamlit / Ollama 进程...
echo.

"%SystemRoot%\System32\taskkill.exe" /f /im python.exe /t >nul 2>&1
"%SystemRoot%\System32\taskkill.exe" /f /im streamlit.exe /t >nul 2>&1
"%SystemRoot%\System32\taskkill.exe" /f /im ollama.exe /t >nul 2>&1

echo.
echo 所有系统已停止！
echo.
pause
