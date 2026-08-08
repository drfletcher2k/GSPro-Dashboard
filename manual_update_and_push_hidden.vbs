Set shell = CreateObject("WScript.Shell")
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""C:\ai-shared\gspro-dashboard\manual_update_and_push.ps1""", 0, False
