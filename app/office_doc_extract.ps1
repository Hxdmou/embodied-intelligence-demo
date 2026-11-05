# ============================================================================
# office_doc_extract.ps1 — 老式.doc文件Word COM离线全文提取（RAG全格式加载桥接）
# 指定 -OutPdf 时改为导出PDF（供纯图版.doc走渲染+离线OCR通道）
# ============================================================================
param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [string]$OutPdf = ''
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $null
try {
    $doc = $word.Documents.Open($FilePath, $false, $true)
    if ($OutPdf) {
        # wdExportFormatPDF = 17
        $doc.ExportAsFixedFormat($OutPdf, 17)
        Write-Output 'PDF_EXPORTED'
    } else {
        Write-Output $doc.Content.Text
    }
} finally {
    if ($doc) { $doc.Close($false) }
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
