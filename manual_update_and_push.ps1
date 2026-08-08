$ErrorActionPreference = "Stop"
Set-Location "C:\ai-shared\gspro-dashboard"
& python "C:\ai-shared\gspro-dashboard\update.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& python "C:\ai-shared\gspro-dashboard\auto_push.py"
exit $LASTEXITCODE
