@echo off
setlocal
title 机器人仿真 + 控制 GUI（便携版）
pushd "%~dp0"

rem ===== 所有路径基于本bat所在目录，U盘换盘符也能跑 =====
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PYEXE=%ROOT%\python\python.exe"
set "PYTHONNOUSERSITE=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%ROOT%\embodied-intelligence"
start "" "%PYEXE%" robot_sim.py
start "" "%PYEXE%" robot_control_gui.py

echo 机器人仿真与控制 GUI 已启动！
pause
