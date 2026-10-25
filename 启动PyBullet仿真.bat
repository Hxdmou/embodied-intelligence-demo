@echo off
setlocal
title PyBullet 机械臂仿真（便携版）
pushd "%~dp0"

rem ===== 所有路径基于本bat所在目录，U盘换盘符也能跑 =====
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PYEXE=%ROOT%\python\python.exe"
set "PYTHONNOUSERSITE=1"
set "PYTHONIOENCODING=utf-8"

echo ==============================================================
echo           PyBullet 机械臂仿真（便携版）
echo ==============================================================
echo.
echo 正在启动 PyBullet 3D 窗口...
echo.
echo 操作:
echo   鼠标左键拖动  - 旋转视角
echo   鼠标右键拖动  - 平移视角
echo   鼠标滚轮      - 缩放
echo   关闭窗口      - 退出
echo.

cd /d "%ROOT%\embodied-intelligence"
"%PYEXE%" pybullet_simulation.py

echo.
echo 仿真已退出。
pause
