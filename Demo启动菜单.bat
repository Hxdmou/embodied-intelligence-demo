@echo off
setlocal
title 具身智能演示菜单（便携版）
pushd "%~dp0"

rem ===== 所有路径基于本bat所在目录，U盘换盘符也能跑 =====
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PYEXE=%ROOT%\python\python.exe"
set "PYTHONNOUSERSITE=1"
set "PYTHONIOENCODING=utf-8"

:menu
cls
echo.
echo ==============================================================
echo           具身智能演示菜单 v1.1（便携版）
echo ==============================================================
echo.
echo   [1] 机械臂智能控制演示（含本地大模型）
echo   [2] RAG 十套知识问答系统（浏览器）
echo   [3] PyBullet 机械臂仿真
echo   [4] PPO 训练智能体演示（500万步）
echo   [5] 部署健康检查演示
echo   [6] 三层编排+AI决策+数字孪生综合演示
echo   [7] PyBullet Panda 仿真演示（框架版）
echo   [8] 断网演示自检（演示前建议先运行）
echo   [0] 退出
echo.
echo ==============================================================
echo.
set /p choice=请输入选项编号:

if "%choice%"=="1" goto robot
if "%choice%"=="2" goto rag
if "%choice%"=="3" goto pbsim
if "%choice%"=="4" goto ppo
if "%choice%"=="5" goto health
if "%choice%"=="6" goto gui
if "%choice%"=="7" goto sim
if "%choice%"=="8" goto selfcheck
if "%choice%"=="0" goto end
goto menu

:robot
call "%ROOT%\start_demo.bat"
goto menu

:rag
call "%ROOT%\一键启动RAG系统.bat"
goto menu

:pbsim
call "%ROOT%\启动PyBullet仿真.bat"
goto menu

:ppo
call "%ROOT%\启动训练好的智能体.bat"
goto menu

:health
cd /d "%ROOT%\_PUBLIC_NTA_OUTPUT\EmbodiedSim-Framework"
"%PYEXE%" examples\deploy_health_check_demo.py
pause
goto menu

:gui
cd /d "%ROOT%\_PUBLIC_NTA_OUTPUT\EmbodiedSim-Framework"
"%PYEXE%" examples\gui_control_demo.py
pause
goto menu

:sim
cd /d "%ROOT%\_PUBLIC_NTA_OUTPUT\EmbodiedSim-Framework"
"%PYEXE%" examples\run_simulation_demo.py
pause
goto menu

:selfcheck
call "%ROOT%\断网演示自检.bat"
goto menu

:end
exit
