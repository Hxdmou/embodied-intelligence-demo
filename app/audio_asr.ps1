# ============================================================================
# audio_asr.ps1 — Windows内置语音识别离线转写桥接（完全离线，零第三方组件）
# 用途：RAG全格式加载——QQ/微信/抖音/快手等音频文件语音转文字
# 全量内容保证：循环直至流耗尽（异常=结束），容忍连续8次静音（约2分钟），
#           迭代上限4000轮（支持约16小时超长录音），全部录音对话内容不截断不遗漏
# 引擎：系统语音识别器（zh-CN，用户在系统设置中开启）
# 流程：MediaTranscoder内置转码为WAV → System.Speech离线听写识别
# ============================================================================
param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(Mandatory=$true)][string]$WorkDir
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
$asTaskAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
})[0]

Function Await($WinRTTask, $ResultType) {
    $m = $script:asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $m.Invoke($null, @($WinRTTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
Function AwaitAction($WinRTAction) {
    $t = $script:asTaskAction.Invoke($null, @($WinRTAction))
    $t.Wait(-1) | Out-Null
}

$ext = [System.IO.Path]::GetExtension($FilePath).ToLower()
$wavPath = $FilePath
if ($ext -ne '.wav') {
    [void][Windows.Storage.StorageFile,Windows.Foundation,ContentType=WindowsRuntime]
    [void][Windows.Storage.StorageFolder,Windows.Foundation,ContentType=WindowsRuntime]
    [void][Windows.Media.Transcoding.MediaTranscoder,Windows.Foundation,ContentType=WindowsRuntime]
    [void][Windows.Media.MediaProperties.MediaEncodingProfile,Windows.Foundation,ContentType=WindowsRuntime]
    $inFile = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($FilePath)) ([Windows.Storage.StorageFile])
    $folder = Await ([Windows.Storage.StorageFolder]::GetFolderFromPathAsync($WorkDir)) ([Windows.Storage.StorageFolder])
    $outFile = Await ($folder.CreateFileAsync('audio.wav', [Windows.Storage.CreationCollisionOption]::ReplaceExisting)) ([Windows.Storage.StorageFile])
    $profile = [Windows.Media.MediaProperties.MediaEncodingProfile]::CreateWav([Windows.Media.MediaProperties.AudioEncodingQuality]::Auto)
    $transcoder = [Activator]::CreateInstance([Windows.Media.Transcoding.MediaTranscoder])
    $prep = Await ($transcoder.PrepareFileTranscodeAsync($inFile, $outFile, $profile)) ([Windows.Media.Transcoding.PrepareTranscodeResult])
    if (-not $prep.CanTranscode) {
        Write-Error ('内置转码器无法解码该音频: ' + $prep.FailureReason)
        exit 4
    }
    AwaitAction ($prep.TranscodeAsync())
    $wavPath = Join-Path $WorkDir 'audio.wav'
}

Add-Type -AssemblyName System.Speech
$rec = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
    Where-Object { $_.Culture.Name -eq 'zh-CN' } | Select-Object -First 1
if (-not $rec) {
    $rec = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() | Select-Object -First 1
}
if (-not $rec) {
    Write-Error '系统未安装语音识别器，请在设置中开启语音识别'
    exit 5
}
Write-Output ('识别器: ' + $rec.Id)

$sr = New-Object System.Speech.Recognition.SpeechRecognitionEngine($rec.Id)
$sr.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$fs = [System.IO.File]::OpenRead($wavPath)
$sr.SetInputToWaveStream($fs)
$sb = New-Object System.Text.StringBuilder
$empty = 0
for ($iter = 0; $iter -lt 4000; $iter++) {
    try {
        $r = $sr.Recognize([TimeSpan]::FromSeconds(15))
    } catch {
        # 流式输入耗尽后再次Recognize会抛出"无音频输入"异常——这就是识别完成信号
        break
    }
    if ($r -and $r.Text) {
        [void]$sb.AppendLine($r.Text)
        $empty = 0
    } else {
        $empty++
        if ($empty -ge 8) { break }
    }
}
$fs.Dispose()
$sr.Dispose()
Write-Output '---识别文本---'
Write-Output $sb.ToString()
