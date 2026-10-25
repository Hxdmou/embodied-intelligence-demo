@echo off
setlocal enabledelayedexpansion

title 垂直领域企业级RAG智能问答系统 V3.1.0
cls
pushd "%~dp0"

rem ===== 所有路径基于本bat所在目录，U盘换盘符也能跑 =====
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

rem ===== 配置Ollama模型目录 =====
rem 模型目录直接用U盘内ollama\models（U盘完全自包含，绝不读C盘模型库）
set "OLLAMA_MODELS=%ROOT%\ollama\models"
if not exist "%OLLAMA_MODELS%\blobs\sha256-a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f" (
    echo.
    echo   [提示] U盘内大模型尚未合并。
    echo   请先双击运行【合并模型到本机.bat】把分卷合并到U盘，完成后再启动本系统。
    echo.
    pause
    exit /b 1
)
set "OLLAMA_HOST=127.0.0.1:11434"

rem ===== 配置RAG系统使用本地Ollama后端 =====
set "LLM_BACKEND=ollama"
set "OLLAMA_BASE_URL=http://127.0.0.1:11434/v1"
set "OLLAMA_MODEL_NAME=qwen3:8b"

rem ===== 配置HuggingFace嵌入模型走U盘内离线缓存 =====
set "HF_HOME=%ROOT%\hf_cache"
set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"
set "PYTHONIOENCODING=utf-8"

rem ===== 断网加固：关闭streamlit遥测（离线环境无需上报）=====
set "STREAMLIT_BROWSER_GATHER_USAGE_STATS=false"

rem ===== 断网加固：强制保证streamlit凭证文件合法 =====
rem 原理：凭证文件不存在时headless模式自动跳过邮箱询问；
rem       凭证文件存在但email非法（非空且不含单个@）时streamlit会启动即闪退。
rem 故此处无条件写入合法的空邮箱（原有文件先备份为credentials.toml.bak）。
set "ST_DIR=%USERPROFILE%\.streamlit"
set "ST_CRED=!ST_DIR!\credentials.toml"
if not exist "!ST_DIR!" mkdir "!ST_DIR!" 2>nul
if exist "!ST_CRED!" copy /y "!ST_CRED!" "!ST_CRED!.bak" >nul 2>nul
> "!ST_CRED!" echo [general]
>> "!ST_CRED!" echo email = ""

rem ===== 便携Python =====
set "PYEXE=%ROOT%\python\python.exe"

:menu
cls
echo.
echo ==============================================================
echo.
echo        垂直领域企业级RAG智能问答系统 V3.1.0
echo.
echo ==============================================================
echo.
echo   本系统使用本地 Ollama 大模型（qwen3:8b），无需联网、无需API Key。
echo.
echo   系统列表：
echo.
echo   [1]  通用RAG智能问答系统        (端口 7861)
echo   [2]  法律知识问答系统           (端口 7869)
echo   [3]  教育知识问答系统           (端口 7870)
echo   [4]  医疗健康问答系统           (端口 7871)
echo   [5]  金融知识问答系统           (端口 7872)
echo   [6]  IT技术问答系统             (端口 7873)
echo   [7]  电商零售问答系统           (端口 7874)
echo   [8]  政务服务问答系统           (端口 7875)
echo   [9]  人力资源问答系统           (端口 7876)
echo   [10] 科研学术问答系统           (端口 7877)
echo.
echo   [11] 一键启动全部10套系统 + 自动打开浏览器
echo   [0]  退出
echo.
echo ==============================================================
echo.
echo   当前目录: %CD%
echo.

set /p choice=  请输入选项编号:

if "%choice%"=="0" goto end
if "%choice%"=="" goto end

rem ===== 检查便携Python =====
if not exist "%PYEXE%" (
    echo.
    echo   [错误] 未找到便携Python: %PYEXE%
    pause
    exit /b 1
)

rem ===== 启动Ollama服务（如未运行）=====
"%SystemRoot%\System32\curl.exe" -f -s -o nul --connect-timeout 2 http://127.0.0.1:11434/api/tags >nul 2>&1
if not errorlevel 1 goto ollama_ready

echo.
echo   正在启动本地大模型服务（Ollama）...
start "OllamaServer" /min "%ROOT%\ollama\ollama.exe" serve

set /a wait=0
:wait_ollama
"%SystemRoot%\System32\ping.exe" -n 3 127.0.0.1 >nul
set /a wait+=2
"%SystemRoot%\System32\curl.exe" -f -s -o nul --connect-timeout 2 http://127.0.0.1:11434/api/tags >nul 2>&1
if not errorlevel 1 goto ollama_ready
if !wait! GEQ 60 (
    echo.
    echo   [错误] Ollama服务60秒内未就绪，请检查电脑内存是否≥16GB。
    pause
    exit /b 1
)
goto wait_ollama

:ollama_ready
echo   本地大模型服务已就绪。

rem ===== 校验qwen3:8b模型已加载（防止被其他Ollama实例占端口）=====
"%SystemRoot%\System32\curl.exe" -f -s --connect-timeout 3 http://127.0.0.1:11434/api/tags | "%SystemRoot%\System32\findstr.exe" /i "qwen3" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [错误] Ollama服务在运行，但未检测到 qwen3:8b 模型！
    echo   可能原因：本机另有其他Ollama占用了11434端口，且不含U盘模型。
    echo   请关闭其他Ollama实例后重试，并确认已运行【合并模型到本机.bat】。
    pause
    exit /b 1
)
echo   已确认 qwen3:8b 模型。

if "%choice%"=="11" goto start_all

echo.
echo   正在启动选中的系统...
echo.

if "%choice%"=="1" (
    start "通用RAG" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run run.py --server.port 7861 --server.headless true"
    set "url=http://localhost:7861"
    goto open_single
)
if "%choice%"=="2" (
    start "法律知识" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run legal_qa.py --server.port 7869 --server.headless true"
    set "url=http://localhost:7869"
    goto open_single
)
if "%choice%"=="3" (
    start "教育知识" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run education_qa.py --server.port 7870 --server.headless true"
    set "url=http://localhost:7870"
    goto open_single
)
if "%choice%"=="4" (
    start "医疗健康" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run medical_qa.py --server.port 7871 --server.headless true"
    set "url=http://localhost:7871"
    goto open_single
)
if "%choice%"=="5" (
    start "金融知识" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run finance_qa.py --server.port 7872 --server.headless true"
    set "url=http://localhost:7872"
    goto open_single
)
if "%choice%"=="6" (
    start "IT技术" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run tech_qa.py --server.port 7873 --server.headless true"
    set "url=http://localhost:7873"
    goto open_single
)
if "%choice%"=="7" (
    start "电商零售" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run e_commerce_qa.py --server.port 7874 --server.headless true"
    set "url=http://localhost:7874"
    goto open_single
)
if "%choice%"=="8" (
    start "政务服务" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run government_qa.py --server.port 7875 --server.headless true"
    set "url=http://localhost:7875"
    goto open_single
)
if "%choice%"=="9" (
    start "人力资源" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run hr_qa.py --server.port 7876 --server.headless true"
    set "url=http://localhost:7876"
    goto open_single
)
if "%choice%"=="10" (
    start "科研学术" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run academic_qa.py --server.port 7877 --server.headless true"
    set "url=http://localhost:7877"
    goto open_single
)

echo.
echo   无效选项，请重新输入。
pause
goto menu

:open_single
echo.
set "port=!url:~-4!"
echo   正在等待服务启动（轮询端口 !port!，最长3分钟，U盘首次加载较慢）...
call :wait_port !port! 180
if errorlevel 1 (
    echo.
    echo   [失败] 端口 !port! 180秒内未就绪，请查看刚打开的黑色cmd窗口中的报错信息。
    pause
    goto end
)
echo   服务已就绪，正在打开浏览器: !url!
start "" "!url!"
echo.
echo   完成！请勿关闭黑色的cmd窗口。
goto end

:start_all
echo.
echo   正在启动全部10套系统，请稍候...
echo.

echo   [1/10] 启动通用RAG智能问答系统 (端口 7861)...
start "通用RAG" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run run.py --server.port 7861 --server.headless true"
"%SystemRoot%\System32\ping.exe" -n 3 127.0.0.1 >nul

echo   [2/10] 启动法律知识问答系统 (端口 7869)...
start "法律知识" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run legal_qa.py --server.port 7869 --server.headless true"
"%SystemRoot%\System32\ping.exe" -n 3 127.0.0.1 >nul

echo   [3/10] 启动教育知识问答系统 (端口 7870)...
start "教育知识" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run education_qa.py --server.port 7870 --server.headless true"
"%SystemRoot%\System32\ping.exe" -n 3 127.0.0.1 >nul

echo   [4/10] 启动医疗健康问答系统 (端口 7871)...
start "医疗健康" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run medical_qa.py --server.port 7871 --server.headless true"
"%SystemRoot%\System32\ping.exe" -n 3 127.0.0.1 >nul

echo   [5/10] 启动金融知识问答系统 (端口 7872)...
start "金融知识" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run finance_qa.py --server.port 7872 --server.headless true"
"%SystemRoot%\System32\ping.exe" -n 3 127.0.0.1 >nul

echo   [6/10] 启动IT技术问答系统 (端口 7873)...
start "IT技术" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run tech_qa.py --server.port 7873 --server.headless true"
"%SystemRoot%\System32\ping.exe" -n 3 127.0.0.1 >nul

echo   [7/10] 启动电商零售问答系统 (端口 7874)...
start "电商零售" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run e_commerce_qa.py --server.port 7874 --server.headless true"
"%SystemRoot%\System32\ping.exe" -n 3 127.0.0.1 >nul

echo   [8/10] 启动政务服务问答系统 (端口 7875)...
start "政务服务" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run government_qa.py --server.port 7875 --server.headless true"
"%SystemRoot%\System32\ping.exe" -n 3 127.0.0.1 >nul

echo   [9/10] 启动人力资源问答系统 (端口 7876)...
start "人力资源" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run hr_qa.py --server.port 7876 --server.headless true"
"%SystemRoot%\System32\ping.exe" -n 3 127.0.0.1 >nul

echo   [10/10] 启动科研学术问答系统 (端口 7877)...
start "科研学术" cmd /k "cd /d "%ROOT%\app" && "%PYEXE%" -m streamlit run academic_qa.py --server.port 7877 --server.headless true"

echo.
echo   正在等待全部服务启动（逐个端口轮询，每端口最长3分钟）...
echo   若某套系统报错，请关闭其窗口后在菜单中重新单独启动。
echo.
set "failed_ports="
call :wait_port 7861 180
if errorlevel 1 ( set "failed_ports=!failed_ports! 7861" ) else ( start "" "http://localhost:7861" )
call :wait_port 7869 180
if errorlevel 1 ( set "failed_ports=!failed_ports! 7869" ) else ( start "" "http://localhost:7869" )
call :wait_port 7870 180
if errorlevel 1 ( set "failed_ports=!failed_ports! 7870" ) else ( start "" "http://localhost:7870" )
call :wait_port 7871 180
if errorlevel 1 ( set "failed_ports=!failed_ports! 7871" ) else ( start "" "http://localhost:7871" )
call :wait_port 7872 180
if errorlevel 1 ( set "failed_ports=!failed_ports! 7872" ) else ( start "" "http://localhost:7872" )
call :wait_port 7873 180
if errorlevel 1 ( set "failed_ports=!failed_ports! 7873" ) else ( start "" "http://localhost:7873" )
call :wait_port 7874 180
if errorlevel 1 ( set "failed_ports=!failed_ports! 7874" ) else ( start "" "http://localhost:7874" )
call :wait_port 7875 180
if errorlevel 1 ( set "failed_ports=!failed_ports! 7875" ) else ( start "" "http://localhost:7875" )
call :wait_port 7876 180
if errorlevel 1 ( set "failed_ports=!failed_ports! 7876" ) else ( start "" "http://localhost:7876" )
call :wait_port 7877 180
if errorlevel 1 ( set "failed_ports=!failed_ports! 7877" ) else ( start "" "http://localhost:7877" )
if defined failed_ports (
    echo.
    echo   [警告] 以下端口180秒内未就绪:!failed_ports!
    echo   请查看对应黑色cmd窗口的报错信息。
)

echo.
echo ==============================================================
echo.
echo           全部10套系统启动完成！
echo.
echo ==============================================================
echo.
echo   访问地址：
echo      [1]  通用RAG智能问答系统:    http://localhost:7861
echo      [2]  法律知识问答系统:       http://localhost:7869
echo      [3]  教育知识问答系统:       http://localhost:7870
echo      [4]  医疗健康问答系统:       http://localhost:7871
echo      [5]  金融知识问答系统:       http://localhost:7872
echo      [6]  IT技术问答系统:         http://localhost:7873
echo      [7]  电商零售问答系统:       http://localhost:7874
echo      [8]  政务服务问答系统:       http://localhost:7875
echo      [9]  人力资源问答系统:       http://localhost:7876
echo      [10] 科研学术问答系统:       http://localhost:7877
echo.
echo   提示：关闭对应黑色cmd窗口即可停止该系统。
echo   浏览器仅在对应服务真正就绪后才会打开，如个别页面未弹出请稍后手动访问上方地址。
echo.

:end
echo.
pause
popd
exit /b

rem ====== 端口就绪轮询子程序（就绪返回0，超时返回1）======
rem %1=端口号 %2=最长等待秒数（用全路径ping延时1秒，兼容PATH受限环境）
:wait_port
set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "!PS_EXE!" set "PS_EXE=powershell"
set /a _w=0
:wait_port_loop
"!PS_EXE!" -NoProfile -Command "try{$t=New-Object Net.Sockets.TcpClient('127.0.0.1',%1);$t.Close();exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 exit /b 0
set /a _w+=1
if !_w! geq %2 exit /b 1
"%SystemRoot%\System32\ping.exe" -n 2 127.0.0.1 >nul
goto wait_port_loop
