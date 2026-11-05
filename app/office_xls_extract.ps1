# ============================================================================
# office_xls_extract.ps1 — 老式.xls文件Excel COM离线全文提取（RAG全格式加载桥接）
# ============================================================================
param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [string]$OutPdf = ''
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
$wb = $null
try {
    $wb = $xl.Workbooks.Open($FilePath, 0, $true)
    if ($OutPdf) {
        # xlTypePDF = 0
        $wb.ExportAsFixedFormat(0, $OutPdf)
        Write-Output 'PDF_EXPORTED'
    } else {
        $sb = New-Object System.Text.StringBuilder
        foreach ($ws in $wb.Worksheets) {
            [void]$sb.AppendLine('=== ' + $ws.Name + ' ===')
            $used = $ws.UsedRange
            if ($null -eq $used) { continue }
            $rows = [Math]::Min($used.Rows.Count, 5000)
            $cols = $used.Columns.Count
            for ($r = 1; $r -le $rows; $r++) {
                $line = @()
                for ($c = 1; $c -le $cols; $c++) {
                    $v = $used.Cells.Item($r, $c).Text
                    if ($v) { $line += $v }
                }
                if ($line.Count -gt 0) { [void]$sb.AppendLine(($line -join "`t")) }
            }
        }
        Write-Output $sb.ToString()
    }
} finally {
    if ($wb) { $wb.Close($false) }
    $xl.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}
