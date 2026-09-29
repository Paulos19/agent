$WshShell = New-Object -ComObject WScript.Shell
$StartupFolder = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $StartupFolder 'AssistenteDevOpsWorker.lnk'
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
$Shortcut.Arguments = 'worker.py'
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.WindowStyle = 7
$Shortcut.Description = 'Assistente DevOps Local Worker'
$Shortcut.Save()

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "[SUCESSO] Inicialização automática configurada!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Atalho criado em: $ShortcutPath"
Write-Host "O Worker agora iniciará sozinho e em segundo plano (sem terminal) sempre que o PC ligar."
