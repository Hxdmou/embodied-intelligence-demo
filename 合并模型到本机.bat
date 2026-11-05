@echo off
%SystemRoot%\System32\chcp.com 936 >nul
setlocal enabledelayedexpansion
title 合并大模型到U盘（首次使用必跑一次）
pushd "%~dp0"

rem ===== 所有路径基于本bat所在目录，U盘换盘符也能跑 =====
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "SRC=%ROOT%\ollama\models"
set "TARGET=%ROOT%\ollama\models"
set "BLOB=sha256-a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f"

echo ==============================================================
echo    合并大模型分卷到U盘（qwen3:8b，4.87GB）
echo ==============================================================
echo.
echo 说明：大模型在U盘内以2个分卷存放，
echo       本脚本把分卷合并到U盘的 ollama\models 目录，
echo       合并后U盘完全自包含，演示时绝不读取C盘模型库。
echo       只需运行一次。
echo.

if exist "%TARGET%\blobs\%BLOB%" (
    echo 检测到U盘已存在合并后的模型，无需重复合并。
    echo 路径: %TARGET%\blobs\%BLOB%
    echo.
    pause
    exit /b 0
)

rem ===== 检查分卷与小文件 =====
if not exist "%SRC%\blobs\qwen3_8b.part1" (
    echo [错误] 未找到分卷1: %SRC%\blobs\qwen3_8b.part1
    pause
    exit /b 1
)
if not exist "%SRC%\blobs\qwen3_8b.part2" (
    echo [错误] 未找到分卷2: %SRC%\blobs\qwen3_8b.part2
    pause
    exit /b 1
)

echo [1/3] 检查小文件（配置/模板/许可/参数/清单）...
set "SMISS="
for %%F in (sha256-05a61d37b08453e59290add468e3bb2f688e23a01e967fecb0e2fa41218cea76 sha256-ae370d884f108d16e7cc8fd5259ebc5773a0afa6e078b11f4ed7e39a27e0dfc4 sha256-d18a5cc71b84bc4af394a31116bd3932b42241de70c77d2b76d69a314ec8aa12 sha256-cff3f395ef3756ab63e58b0ad1b32bb6f802905cae1472e6a12034e4246fbbdb) do (
    if not exist "%SRC%\blobs\%%F" set "SMISS=!SMISS! %%F"
)
if not exist "%SRC%\manifests\registry.ollama.ai\library\qwen3\8b" set "SMISS=!SMISS! manifest-qwen3-8b"
if defined SMISS (
    echo [错误] 缺少小文件:!SMISS!
    pause
    exit /b 1
)
echo       小文件齐全。

echo [2/3] 合并大模型分卷（约4.87GB，请耐心等待1-3分钟）...
copy /b "%SRC%\blobs\qwen3_8b.part1" + "%SRC%\blobs\qwen3_8b.part2" "%TARGET%\blobs\%BLOB%" >nul
if errorlevel 1 (
    echo [错误] 合并失败，请检查U盘剩余空间是否≥6GB。
    pause
    exit /b 1
)

echo [3/3] 校验文件大小...
for %%F in ("%TARGET%\blobs\%BLOB%") do set "FSIZE=%%~zF"
if "!FSIZE!"=="5225374496" (
    echo 校验通过：5225374496 字节，模型完整。
) else (
    echo [错误] 大小不符：!FSIZE! 字节（应为5225374496）。
    echo        请删除 %TARGET%\blobs\%BLOB% 后重新运行本脚本。
    pause
    exit /b 1
)

echo.
echo ==============================================================
echo  合并完成！模型位置: %TARGET%
echo  现在可以运行【一键启动RAG系统.bat】或【Demo启动菜单.bat】。
echo ==============================================================
echo.
pause
