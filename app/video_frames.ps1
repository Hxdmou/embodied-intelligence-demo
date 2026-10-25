# ============================================================================
# video_frames.ps1 — Windows内置MediaComposition视频抽帧桥接（完全离线，零第三方组件）
# 用途：RAG全格式加载——视频按时长均分抽帧供离线OCR
# 合同：-FilePath 视频路径  -OutDir 输出目录  -Frames 帧数（默认30，钳制1..200）
#       -Width -Height 缩略图请求分辨率（默认1920x1080，钳制128..7680/4320，4K/8K源高清OCR）
#       输出 frame_0000.png ...（内容为JPEG，OCR按内容解码与扩展名无关）
#       时长均分采样与源帧率无关——30帧/60帧乃至任意帧率源天然支持；
#       MediaFoundation解码与源分辨率无关——4K/8K源天然支持
# 技术路线（probe_video14实证，全部vtable槽位已验证）：
#   1. MediaComposition.GetThumbnailAsync → IAsyncOperation<IRandomAccessStream>
#      参数化IID运行时GetIids(槽3)发现，等待=IAsyncInfo槽7，GetResults=槽8
#   2. GetResults返回identity指针——严禁直接调槽，先QI到反射IID：
#      IInputStream=[Windows.Storage.Streams.IInputStream].GUID，ReadAsync=槽6
#   3. ReadAsync返回IAsyncOperationWithProgress<IBuffer,uint>（指针即该接口）：
#      IAsyncInfo槽7轮询等待，GetResults=槽10（无需QI），IBuffer.get_Length=槽7
#   4. 字节取出：DataReader.FromBuffer(我方Buffer).ReadBytes（纯投影，
#      不走IBufferByteAccess——该QI在本机E_NOINTERFACE已实证为死路）
# ============================================================================
param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(Mandatory=$true)][string]$OutDir,
    [int]$Frames = 30,
    [int]$Width = 1920,
    [int]$Height = 1080
)
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -Namespace 'Win32' -Name 'K32' -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError=true)]
public static extern bool IsBadReadPtr(System.IntPtr lp, System.UIntPtr ucb);
'@

Function Test-Ptr([IntPtr]$P, [int]$Bytes) {
    if ($P -eq [IntPtr]::Zero) { return $false }
    return -not [Win32.K32]::IsBadReadPtr($P, [UIntPtr]::new([uint64]$Bytes))
}

if (-not (Test-Path -LiteralPath $FilePath)) {
    [Console]::WriteLine('视频文件不存在: ' + $FilePath)
    exit 1
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
if ($Frames -lt 1) { $Frames = 1 }
if ($Frames -gt 200) { $Frames = 200 }
if ($Width -lt 128) { $Width = 128 }
if ($Width -gt 7680) { $Width = 7680 }
if ($Height -lt 128) { $Height = 128 }
if ($Height -gt 4320) { $Height = 4320 }
if ($Width % 2 -eq 1) { $Width++ }
if ($Height % 2 -eq 1) { $Height++ }

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

Function Get-DelegateType([Type[]]$paramTypes, [Type]$returnType, [string]$Name) {
    $domain = [AppDomain]::CurrentDomain
    $asmName = New-Object System.Reflection.AssemblyName('DynDelegateVF')
    $asm = $domain.DefineDynamicAssembly($asmName, [System.Reflection.Emit.AssemblyBuilderAccess]::Run)
    $mod = $asm.DefineDynamicModule('DynDelegateVF')
    $attrs = [System.Reflection.TypeAttributes]::Public -bor [System.Reflection.TypeAttributes]::Sealed -bor [System.Reflection.TypeAttributes]::AutoClass
    $tb = $mod.DefineType($Name, $attrs, [System.MulticastDelegate])
    $ctorParams = [Type[]]@([Object], [IntPtr])
    $ctor = $tb.DefineConstructor(([System.Reflection.MethodAttributes]::Public -bor [System.Reflection.MethodAttributes]::HideBySig -bor [System.Reflection.MethodAttributes]::RTSpecialName), [System.Reflection.CallingConventions]::Standard, $ctorParams)
    $ctor.SetImplementationFlags([System.Reflection.MethodImplAttributes]::Runtime -bor [System.Reflection.MethodImplAttributes]::Managed)
    $mAttrs = [System.Reflection.MethodAttributes]::Public -bor [System.Reflection.MethodAttributes]::HideBySig -bor [System.Reflection.MethodAttributes]::NewSlot -bor [System.Reflection.MethodAttributes]::Virtual
    $mb = $tb.DefineMethod('Invoke', $mAttrs, $returnType, $paramTypes)
    $mb.SetImplementationFlags([System.Reflection.MethodImplAttributes]::Runtime -bor [System.Reflection.MethodImplAttributes]::Managed)
    return $tb.CreateType()
}

Function Append-Clip($ClipsObj, $ClipObj) {
    $clipsUnk = [System.Runtime.InteropServices.Marshal]::GetIUnknownForObject($ClipsObj)
    try {
        $vtbl = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($clipsUnk)
        $slotAddr = [IntPtr]::new($vtbl.ToInt64() + 13 * [IntPtr]::Size)
        $appendPtr = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($slotAddr)
        $append = [System.Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer($appendPtr, $script:appendType)
        $clipUnk = [System.Runtime.InteropServices.Marshal]::GetIUnknownForObject($ClipObj)
        try {
            $hr = $append.Invoke($clipsUnk, $clipUnk)
            if ($hr -ne 0) { throw "IVector::Append HRESULT=0x{0:X8}" -f $hr }
        } finally {
            [System.Runtime.InteropServices.Marshal]::Release($clipUnk) | Out-Null
        }
    } finally {
        [System.Runtime.InteropServices.Marshal]::Release($clipsUnk) | Out-Null
    }
}

Function Read-VtblFn($Ptr, [int]$Slot, $DelType) {
    $vtbl = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($Ptr)
    $fnPtr = [System.Runtime.InteropServices.Marshal]::ReadIntPtr([IntPtr]::new($vtbl.ToInt64() + $Slot * [IntPtr]::Size))
    [System.Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer($fnPtr, $DelType)
}

Function Invoke-QI($Ptr, [Guid]$Iid) {
    if (-not (Test-Ptr $Ptr 16)) { return [IntPtr]::Zero }
    $qi = Read-VtblFn $Ptr 0 $script:qiType
    $iidBuf = [System.Runtime.InteropServices.Marshal]::AllocHGlobal(16)
    [System.Runtime.InteropServices.Marshal]::Copy($Iid.ToByteArray(), 0, $iidBuf, 16)
    $qOutBuf = [System.Runtime.InteropServices.Marshal]::AllocHGlobal([IntPtr]::Size)
    [System.Runtime.InteropServices.Marshal]::WriteIntPtr($qOutBuf, [IntPtr]::Zero)
    $hr = $qi.Invoke($Ptr, $iidBuf, $qOutBuf)
    [System.Runtime.InteropServices.Marshal]::FreeHGlobal($iidBuf)
    if ($hr -ne 0) {
        [System.Runtime.InteropServices.Marshal]::FreeHGlobal($qOutBuf)
        return [IntPtr]::Zero
    }
    $p = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($qOutBuf)
    [System.Runtime.InteropServices.Marshal]::FreeHGlobal($qOutBuf)
    return $p
}

Function Get-Iids($Ptr) {
    $getIids = Read-VtblFn $Ptr 3 $script:getIidsType
    $cntBuf = [System.Runtime.InteropServices.Marshal]::AllocHGlobal(4)
    $arrBuf = [System.Runtime.InteropServices.Marshal]::AllocHGlobal([IntPtr]::Size)
    [System.Runtime.InteropServices.Marshal]::WriteInt32($cntBuf, 0)
    [System.Runtime.InteropServices.Marshal]::WriteIntPtr($arrBuf, [IntPtr]::Zero)
    $candidates = @()
    $hr = $getIids.Invoke($Ptr, $cntBuf, $arrBuf)
    if ($hr -eq 0) {
        $cnt = [System.Runtime.InteropServices.Marshal]::ReadInt32($cntBuf)
        $arrPtr = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($arrBuf)
        if ($arrPtr -ne [IntPtr]::Zero -and $cnt -gt 0) {
            $bytes = New-Object byte[] ($cnt * 16)
            [System.Runtime.InteropServices.Marshal]::Copy($arrPtr, $bytes, 0, $cnt * 16)
            for ($k = 0; $k -lt $cnt; $k++) {
                $gb = New-Object byte[] 16
                [Array]::Copy($bytes, $k * 16, $gb, 0, 16)
                $g = [System.Guid]::new($gb)
                $gs = $g.ToString()
                $d1 = [uint32]('0x' + $gs.Substring(0, 8))
                if ($d1 -lt 0x10000) { continue }
                if ($gs -eq 'af86e2e0-b12d-4c6a-9c5a-d7aa65101e90') { continue }
                if ($gs -eq '94ea2b94-e9cc-49e0-c0ff-ee64ca8f5b90') { continue }
                $candidates += $g
            }
            [System.Runtime.InteropServices.Marshal]::FreeCoTaskMem($arrPtr)
        }
    }
    [System.Runtime.InteropServices.Marshal]::FreeHGlobal($cntBuf)
    [System.Runtime.InteropServices.Marshal]::FreeHGlobal($arrBuf)
    return ,$candidates
}

Function Wait-AsyncOp($OpPtr) {
    $info = Invoke-QI $OpPtr $script:iidAsyncInfo
    if ($info -eq [IntPtr]::Zero) { return -1 }
    try {
        $fn = Read-VtblFn $info 7 $script:getStatusType
        $buf = [System.Runtime.InteropServices.Marshal]::AllocHGlobal(4)
        [System.Runtime.InteropServices.Marshal]::WriteInt32($buf, 0)
        $st = 0
        for ($p = 0; $p -lt 600; $p++) {
            $hr = $fn.Invoke($info, $buf)
            $st = [System.Runtime.InteropServices.Marshal]::ReadInt32($buf)
            if ($st -ne 0) { break }
            Start-Sleep -Milliseconds 100
        }
        [System.Runtime.InteropServices.Marshal]::FreeHGlobal($buf)
        return $st
    } finally {
        [System.Runtime.InteropServices.Marshal]::Release($info) | Out-Null
    }
}

Function Get-OpResultPtr($OpPtr, [Guid]$Iid, [int]$Slot) {
    $tp = Invoke-QI $OpPtr $Iid
    if ($tp -eq [IntPtr]::Zero) { return [IntPtr]::Zero }
    try {
        if (-not (Test-Ptr $tp 16)) { return [IntPtr]::Zero }
        $vtbl = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($tp)
        if (-not (Test-Ptr $vtbl ([IntPtr]::Size * ($Slot + 1)))) { return [IntPtr]::Zero }
        $gr = Read-VtblFn $tp $Slot $script:getResultsType
        $resBuf = [System.Runtime.InteropServices.Marshal]::AllocHGlobal([IntPtr]::Size)
        [System.Runtime.InteropServices.Marshal]::WriteIntPtr($resBuf, [IntPtr]::Zero)
        $hr = $gr.Invoke($tp, $resBuf)
        if ($hr -ne 0) {
            [System.Runtime.InteropServices.Marshal]::FreeHGlobal($resBuf)
            return [IntPtr]::Zero
        }
        $rp = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($resBuf)
        [System.Runtime.InteropServices.Marshal]::FreeHGlobal($resBuf)
        return $rp
    } finally {
        [System.Runtime.InteropServices.Marshal]::Release($tp) | Out-Null
    }
}

# 委托类型
$script:appendType     = Get-DelegateType @([IntPtr], [IntPtr]) ([Int32]) 'AppendDelVF'
$script:getStatusType  = Get-DelegateType @([IntPtr], [IntPtr]) ([Int32]) 'StatusDelVF'
$script:getIidsType    = Get-DelegateType @([IntPtr], [IntPtr], [IntPtr]) ([Int32]) 'IidsDelVF'
$script:qiType         = Get-DelegateType @([IntPtr], [IntPtr], [IntPtr]) ([Int32]) 'QiDelVF'
$script:getResultsType = Get-DelegateType @([IntPtr], [IntPtr]) ([Int32]) 'ResultsDelVF'
$script:closeType      = Get-DelegateType @([IntPtr]) ([Int32]) 'CloseDelVF'
$script:getSizeType    = Get-DelegateType @([IntPtr], [IntPtr]) ([Int32]) 'GetSizeDelVF'
$script:readAsyncType  = Get-DelegateType @([IntPtr], [IntPtr], [Int32], [Int32], [IntPtr]) ([Int32]) 'ReadAsyncDelVF'
$script:getLenType     = Get-DelegateType @([IntPtr], [IntPtr]) ([Int32]) 'GetLenDelVF'

# 固定IID
$script:iidAsyncInfo = [Guid]'00000036-0000-0000-c000-000000000046'
$script:targetIid  = $null
$script:iidIBuffer = $null

[void][Windows.Storage.StorageFile,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Storage.Streams.IRandomAccessStream,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Storage.Streams.IInputStream,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Storage.Streams.Buffer,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Storage.Streams.DataReader,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Media.Editing.MediaClip,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Media.Editing.MediaComposition,Windows.Foundation,ContentType=WindowsRuntime]
[void][Windows.Media.Editing.VideoFramePrecision,Windows.Foundation,ContentType=WindowsRuntime]

$script:iidIInputStream = [Windows.Storage.Streams.IInputStream].GUID

Function Discover-IBufferIid() {
    $tmp = [Activator]::CreateInstance([Windows.Storage.Streams.Buffer], @([uint32]16))
    $u = [System.Runtime.InteropServices.Marshal]::GetIUnknownForObject($tmp)
    try {
        $cands = Get-Iids $u
        foreach ($c in $cands) { return $c }
        return $null
    } finally {
        [System.Runtime.InteropServices.Marshal]::Release($u) | Out-Null
    }
}

Function Read-StreamToFile($StreamPtr, $OutPath) {
    if (-not (Test-Ptr $StreamPtr 16)) { return $false }
    if ($script:iidIInputStream -eq [Guid]::Empty) { return $false }
    $inStream = Invoke-QI $StreamPtr $script:iidIInputStream
    if ($inStream -eq [IntPtr]::Zero) { return $false }
    if (-not $script:iidIBuffer) { $script:iidIBuffer = Discover-IBufferIid }

    $ms = New-Object System.IO.MemoryStream
    $chunk = 262144
    $total = [int64]0
    $guard = 0
    $eof = $false
    $readAsync = Read-VtblFn $inStream 6 $script:readAsyncType
    try {
        while (-not $eof -and $guard -lt 200000) {
            $guard++
            $opPtr2 = [IntPtr]::Zero
            $bufObjUnk = [IntPtr]::Zero
            $ibufPtr = [IntPtr]::Zero
            $resBufPtr = [IntPtr]::Zero
            try {
                $bufObj = [Activator]::CreateInstance([Windows.Storage.Streams.Buffer], @([uint32]$chunk))
                $bufObjUnk = [System.Runtime.InteropServices.Marshal]::GetIUnknownForObject($bufObj)
                if ($script:iidIBuffer) { $ibufPtr = Invoke-QI $bufObjUnk $script:iidIBuffer }
                if ($ibufPtr -eq [IntPtr]::Zero) { $ibufPtr = $bufObjUnk }

                $raBuf = [System.Runtime.InteropServices.Marshal]::AllocHGlobal([IntPtr]::Size)
                [System.Runtime.InteropServices.Marshal]::WriteIntPtr($raBuf, [IntPtr]::Zero)
                $hr = $readAsync.Invoke($inStream, $ibufPtr, $chunk, 0, $raBuf)
                $opPtr2 = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($raBuf)
                [System.Runtime.InteropServices.Marshal]::FreeHGlobal($raBuf)
                if ($hr -ne 0 -or $opPtr2 -eq [IntPtr]::Zero) { return $false }

                $st = Wait-AsyncOp $opPtr2
                if ($st -ne 1) { return $false }

                if (-not (Test-Ptr $opPtr2 16)) { return $false }
                $vtbl2 = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($opPtr2)
                if (-not (Test-Ptr $vtbl2 ([IntPtr]::Size * 11))) { return $false }
                $gr = Read-VtblFn $opPtr2 10 $script:getResultsType
                $resBuf = [System.Runtime.InteropServices.Marshal]::AllocHGlobal([IntPtr]::Size)
                [System.Runtime.InteropServices.Marshal]::WriteIntPtr($resBuf, [IntPtr]::Zero)
                $hr = $gr.Invoke($opPtr2, $resBuf)
                $resBufPtr = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($resBuf)
                [System.Runtime.InteropServices.Marshal]::FreeHGlobal($resBuf)
                if ($hr -ne 0 -or $resBufPtr -eq [IntPtr]::Zero -or -not (Test-Ptr $resBufPtr 16)) { return $false }

                $getLen = Read-VtblFn $resBufPtr 7 $script:getLenType
                $lenBuf = [System.Runtime.InteropServices.Marshal]::AllocHGlobal(4)
                [System.Runtime.InteropServices.Marshal]::WriteInt32($lenBuf, 0)
                $hr = $getLen.Invoke($resBufPtr, $lenBuf)
                $got = [System.Runtime.InteropServices.Marshal]::ReadInt32($lenBuf)
                [System.Runtime.InteropServices.Marshal]::FreeHGlobal($lenBuf)
                if ($hr -ne 0) { return $false }
                if ($got -eq 0) { $eof = $true; break }

                $reader = [Windows.Storage.Streams.DataReader]::FromBuffer($bufObj)
                try {
                    $arr = New-Object byte[] $got
                    $reader.ReadBytes($arr)
                } finally {
                    $reader.Dispose()
                }
                $ms.Write($arr, 0, $got)
                $total += $got
                if ($got -lt $chunk) { $eof = $true }
            } finally {
                if ($resBufPtr -ne [IntPtr]::Zero) { [System.Runtime.InteropServices.Marshal]::Release($resBufPtr) | Out-Null }
                if ($opPtr2 -ne [IntPtr]::Zero) { [System.Runtime.InteropServices.Marshal]::Release($opPtr2) | Out-Null }
                if ($ibufPtr -ne [IntPtr]::Zero -and $ibufPtr -ne $bufObjUnk) { [System.Runtime.InteropServices.Marshal]::Release($ibufPtr) | Out-Null }
                if ($bufObjUnk -ne [IntPtr]::Zero) { [System.Runtime.InteropServices.Marshal]::Release($bufObjUnk) | Out-Null }
            }
        }
        if ($total -eq 0) { return $false }
        [System.IO.File]::WriteAllBytes($OutPath, $ms.ToArray())
        return $true
    } finally {
        $ms.Dispose()
        [System.Runtime.InteropServices.Marshal]::Release($inStream) | Out-Null
    }
}

Function Get-FrameAt($Comp, [int64]$Ms, $OutPath) {
    $op = $Comp.GetThumbnailAsync([TimeSpan]::FromMilliseconds($Ms), $Width, $Height, [Windows.Media.Editing.VideoFramePrecision]::NearestFrame)
    $unk = [System.Runtime.InteropServices.Marshal]::GetIUnknownForObject($op)
    $streamPtr = [IntPtr]::Zero
    try {
        if (-not $script:targetIid) {
            $cands = Get-Iids $unk
            if ($cands.Count -ge 1) { $script:targetIid = $cands[0] }
        }
        if (-not $script:targetIid) { return $false }

        $st = Wait-AsyncOp $unk
        if ($st -ne 1) { return $false }

        $streamPtr = Get-OpResultPtr $unk $script:targetIid 8
        if ($streamPtr -eq [IntPtr]::Zero) { return $false }

        $ok = Read-StreamToFile $streamPtr $OutPath
        $info = Invoke-QI $unk $script:iidAsyncInfo
        if ($info -ne [IntPtr]::Zero) {
            $close = Read-VtblFn $info 10 $script:closeType
            $close.Invoke($info) | Out-Null
            [System.Runtime.InteropServices.Marshal]::Release($info) | Out-Null
        }
        return $ok
    } finally {
        if ($streamPtr -ne [IntPtr]::Zero) { [System.Runtime.InteropServices.Marshal]::Release($streamPtr) | Out-Null }
        [System.Runtime.InteropServices.Marshal]::Release($unk) | Out-Null
    }
}

try {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($FilePath)) ([Windows.Storage.StorageFile])
    $clip = Await ([Windows.Media.Editing.MediaClip]::CreateFromFileAsync($file)) ([Windows.Media.Editing.MediaClip])
    $comp = [Activator]::CreateInstance([Windows.Media.Editing.MediaComposition])
    Append-Clip $comp.Clips $clip
    $durMs = $clip.OriginalDuration.TotalMilliseconds
    [Console]::WriteLine(('视频时长: {0:N1}秒 计划抽帧: {1} 请求分辨率: {2}x{3}' -f ($durMs / 1000), $Frames, $Width, $Height))

    $okCount = 0
    for ($i = 0; $i -lt $Frames; $i++) {
        $ms = [int64]($durMs * ($i + 0.5) / $Frames)
        $outPath = Join-Path $OutDir ('frame_{0:D4}.png' -f $i)
        $ok = Get-FrameAt $comp $ms $outPath
        if ($ok -eq $true) {
            $okCount++
        } else {
            if (Test-Path -LiteralPath $outPath) { Remove-Item -LiteralPath $outPath -Force }
        }
    }
    [Console]::WriteLine(('抽帧完成: 成功{0}/{1}' -f $okCount, $Frames))
    if ($okCount -eq 0) { exit 1 }
    exit 0
} catch {
    [Console]::WriteLine('抽帧异常: ' + $_.Exception.Message)
    exit 1
}
