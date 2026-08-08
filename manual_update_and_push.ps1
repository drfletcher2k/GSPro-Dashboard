$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logPath = Join-Path $projectDir "manual_update.log"

function Show-Result($message, $title, $iconName) {
    $icon = [System.Windows.Forms.MessageBoxIcon]::$iconName
    [System.Windows.Forms.MessageBox]::Show($message, $title, 'OK', $icon) | Out-Null
}

Set-Location $projectDir
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Manual update started" | Set-Content -LiteralPath $logPath

try {
    $output = & python (Join-Path $projectDir "update_now.py") 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    Add-Content -LiteralPath $logPath -Value $output.TrimEnd()
    if ($exitCode -ne 0) {
        throw $output
    }
    Show-Result "GSPro dashboard update completed successfully.`r`n`r`nLog: $logPath" "GSPro Dashboard" "Information"
    exit 0
} catch {
    Add-Content -LiteralPath $logPath -Value $_.Exception.Message
    Show-Result "GSPro dashboard update failed.`r`n`r`n$($_.Exception.Message)`r`nSee log: $logPath" "GSPro Dashboard" "Error"
    exit 1
}
