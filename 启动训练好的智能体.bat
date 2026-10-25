@echo off
setlocal
title PPO 训练智能体演示（便携版）
pushd "%~dp0"

rem ===== 所有路径基于本bat所在目录，U盘换盘符也能跑 =====
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PYEXE=%ROOT%\python\python.exe"
set "PYTHONNOUSERSITE=1"
set "PYTHONIOENCODING=utf-8"

echo ==============================================================
echo   PPO 训练机械臂 - 500万步 0%% 失败率（便携版）
echo ==============================================================
echo.
echo 正在加载训练好的模型...
echo.
echo 操作:
echo   鼠标左键拖动  - 旋转视角
echo   鼠标右键拖动  - 平移视角
echo   鼠标滚轮      - 缩放
echo   关闭窗口      - 退出
echo.

cd /d "%ROOT%\embodied-intelligence"
"%PYEXE%" demo_trained_agent.py

echo.
echo 演示已退出。
pause
