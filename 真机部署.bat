@echo off
setlocal
%SystemRoot%\System32\chcp.com 936 >nul
title 真机部署（便携版）
pushd "%~dp0"

rem ===== 所有路径基于本bat所在目录，U盘换盘符也能跑 =====
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PYEXE=%ROOT%\python\python.exe"
set "PYTHONNOUSERSITE=1"
set "PYTHONIOENCODING=utf-8"

echo ==============================================================
echo             真机部署（便携版） v1.0
echo     具身智能工程化部署 / Sim2Real / 多协议通信适配
echo ==============================================================
echo.
echo   说明: 真机底层驱动包内置于 embodied-intelligence\，
echo         本接口仅负责调用，不包含任何驱动源码。
echo.

cd /d "%ROOT%\embodied-intelligence"
"%PYEXE%" real_deploy_entry.py

%SystemRoot%\System32\chcp.com 936 >nul
echo.
echo 真机部署流程已退出。
pause
