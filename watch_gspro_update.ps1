$Project = "C:\Users\danfl\OneDrive\Stuff\GSPro Dashboard"
$WasRunning = $false

while ($true) {
    $Running = Get-Process | Where-Object { $_.ProcessName -like "GSPro*" }

    if ($Running) {
        $WasRunning = $true
    }

    if (-not $Running -and $WasRunning) {
        Start-Sleep -Seconds 30
        Set-Location $Project
        python update.py
        $WasRunning = $false
    }

    Start-Sleep -Seconds 60
}