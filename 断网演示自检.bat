@echo off
setlocal enabledelayedexpansion
title 断网演示自检（便携版）v1.0
pushd "%~dp0"

rem ===== 所有路径基于本bat所在目录，U盘换盘符也能跑 =====
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PYEXE=%ROOT%\python\python.exe"
set /a PASS=0
set /a FAIL=0

echo ==============================================================
echo    断网演示自检工具 v1.0（全程无需联网）
echo ==============================================================
echo.
echo   当前目录: %ROOT%
echo.

rem ---------- 1. 便携Python ----------
if exist "%PYEXE%" (
    call :ok "便携Python（python\python.exe）"
) else (
    call :bad "缺少便携Python: python\python.exe"
)

rem ---------- 2. Python依赖包 ----------
echo   [..] 正在检查Python依赖包（约10秒）...
"%PYEXE%" -c "import importlib.util as u;mods=['streamlit','langchain','langchain_openai','langchain_community','langchain_huggingface','langchain_text_splitters','faiss','sentence_transformers','torch','pybullet','pybullet_data','numpy','dotenv','openai','pypdf','docx2txt','stable_baselines3','gymnasium','PyQt5'];missing=[m for m in mods if u.find_spec(m) is None];print('MISSING='+','.join(missing)) if missing else print('ALLPKGSOK')" > "%TEMP%\_usb_selfchk.out" 2>&1
"%SystemRoot%\System32\findstr.exe" /c:"ALLPKGSOK" "%TEMP%\_usb_selfchk.out" >nul 2>&1
if not errorlevel 1 (
    call :ok "Python依赖包齐全（19项，含streamlit/torch/pybullet/PyQt5）"
) else (
    call :bad "Python依赖包有缺失，明细: %TEMP%\_usb_selfchk.out"
)

rem ---------- 3. 嵌入模型离线缓存 ----------
set "SNAPFOUND="
for /r "%ROOT%\hf_cache\hub\models--shibing624--text2vec-base-chinese\snapshots" %%F in (model.safetensors) do (
    if exist "%%F" set "SNAPFOUND=1"
)
if defined SNAPFOUND (
    call :ok "嵌入模型 text2vec-base-chinese 离线缓存（hf_cache）"
) else (
    call :bad "缺少嵌入模型离线缓存: hf_cache\hub\models--shibing624--text2vec-base-chinese"
)

rem ---------- 4. 便携Ollama ----------
if exist "%ROOT%\ollama\ollama.exe" (
    call :ok "便携Ollama（ollama\ollama.exe）"
) else (
    call :bad "缺少便携Ollama: ollama\ollama.exe"
)

rem ---------- 5. 大模型已合并 ----------
set "BLOB=%ROOT%\ollama\models\blobs\sha256-a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f"
if exist "%BLOB%" (
    for %%F in ("%BLOB%") do set "BSZ=%%~zF"
    if "!BSZ!"=="5225374496" (
        call :ok "大模型 qwen3:8b 已在U盘内合并（5225374496字节）"
    ) else (
        call :bad "模型文件大小不符: !BSZ! 字节（应为5225374496），请删除后重新运行【合并模型到本机.bat】"
    )
) else (
    call :bad "U盘内大模型尚未合并，请先运行【合并模型到本机.bat】（合并到U盘，只需一次）"
)

rem ---------- 6. RAG十套入口文件 ----------
set "SYSMISS="
for %%N in (run legal_qa education_qa medical_qa finance_qa tech_qa e_commerce_qa government_qa hr_qa academic_qa) do (
    if not exist "%ROOT%\app\%%N.py" set "SYSMISS=!SYSMISS! %%N.py"
)
if defined SYSMISS (
    call :bad "RAG入口文件缺失:!SYSMISS!"
) else (
    call :ok "RAG十套系统入口文件齐全"
)

rem ---------- 7. FAISS向量索引 ----------
set "IDXMISS="
for %%D in (general legal education medical finance tech e_commerce government hr academic) do (
    if not exist "%ROOT%\app\%%D_faiss_index\index.faiss" set "IDXMISS=!IDXMISS! %%D"
    if not exist "%ROOT%\app\%%D_faiss_index\index.pkl" set "IDXMISS=!IDXMISS! %%D-pkl"
)
if defined IDXMISS (
    call :bad "FAISS索引缺失:!IDXMISS!"
) else (
    call :ok "十套系统FAISS向量索引齐全"
)

rem ---------- 8. 机器人演示文件 ----------
set "RMISS="
for %%F in (demo_robot_gui.py demo_trained_agent.py pybullet_simulation.py robot_sim.py robot_control_gui.py ollama_client.py ppo_kuka_reach_finetuned_best.zip) do (
    if not exist "%ROOT%\embodied-intelligence\%%F" set "RMISS=!RMISS! %%F"
)
if defined RMISS (
    call :bad "机器人演示文件缺失:!RMISS!"
) else (
    call :ok "机器人演示脚本与训练模型文件齐全"
)

rem ---------- 9. 框架演示 ----------
set "EMISS="
for %%F in (deploy_health_check_demo.py gui_control_demo.py run_simulation_demo.py) do (
    if not exist "%ROOT%\_PUBLIC_NTA_OUTPUT\EmbodiedSim-Framework\examples\%%F" set "EMISS=!EMISS! %%F"
)
if defined EMISS (
    call :bad "框架演示脚本缺失:!EMISS!"
) else (
    call :ok "框架演示脚本齐全"
)

rem ---------- 10. 核心脚本语法完整性 ----------
echo   [..] 正在编译校验核心脚本...
"%PYEXE%" -m py_compile "%ROOT%\app\rag.py" "%ROOT%\app\run.py" "%ROOT%\embodied-intelligence\demo_robot_gui.py" "%ROOT%\embodied-intelligence\demo_trained_agent.py" "%ROOT%\embodied-intelligence\pybullet_simulation.py" "%ROOT%\_PUBLIC_NTA_OUTPUT\EmbodiedSim-Framework\examples\deploy_health_check_demo.py" "%ROOT%\_PUBLIC_NTA_OUTPUT\EmbodiedSim-Framework\examples\gui_control_demo.py" "%ROOT%\_PUBLIC_NTA_OUTPUT\EmbodiedSim-Framework\examples\run_simulation_demo.py" >nul 2>"%TEMP%\_usb_selfchk_compile.out"
if not errorlevel 1 (
    call :ok "核心脚本编译校验通过（无损坏）"
) else (
    call :bad "核心脚本编译失败，明细: %TEMP%\_usb_selfchk_compile.out"
)

rem ---------- 汇总 ----------
echo.
echo ==============================================================
echo    自检完成: 通过 !PASS! 项, 失败 !FAIL! 项
echo ==============================================================
if !FAIL! EQU 0 (
    echo.
    echo   [结论] 全部检查通过！本U盘可在完全断网环境下演示:
    echo     1. RAG十套知识问答系统（本地大模型，无需联网）
    echo     2. 机械臂智能控制演示（含本地大模型）
    echo     3. PyBullet仿真 / PPO训练智能体 / 框架综合演示
    echo.
) else (
    echo.
    echo   [结论] 存在失败项，请按上方[失败]提示逐项修复后再做断网演示！
    echo.
)
pause
exit /b

:ok
set /a PASS+=1
echo   [通过] %~1
exit /b 0

:bad
set /a FAIL+=1
echo   [失败] %~1
exit /b 0
