# ============================================================================
# ocr_bridge.ps1 — Windows内置OCR桥接（完全离线，零第三方组件）
# 用途：为RAG知识问答系统识别纯图版/水印版/防伪版/红框标记版文件
# 输入：-ListFile 指向UTF-8文本文件，每行一个图片绝对路径
# 输出：每张图片的识别文本，页间以 <<<PAGE>>> 分隔
# ============================================================================
param(
    [Parameter(Mandatory=$true)][string]$ListFile
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetGenericArguments().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

Function Await($WinRTTask, $ResultType) {
    $m = $script:asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $m.Invoke($null, @($WinRTTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

[void][Windows.Storage.StorageFile,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) {
    Write-Error '系统未安装OCR语言包，无法识别'
    exit 2
}

$paths = Get-Content -LiteralPath $ListFile -Encoding UTF8
$out = New-Object System.Text.StringBuilder

foreach ($p in $paths) {
    $p = $p.Trim()
    if (-not $p) { continue }
    $stream = $null
    try {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($p)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        [void]$out.AppendLine($result.Text)
    } catch {
        [void]$out.AppendLine('[OCR-FAIL] ' + $_.Exception.Message)
    } finally {
        if ($stream) { $stream.Dispose() }
    }
    [void]$out.AppendLine('<<<PAGE>>>')
}

Write-Output $out.ToString()
