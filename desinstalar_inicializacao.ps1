$StartupFolder = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $StartupFolder 'AssistenteDevOpsWorker.lnk'
if (Test-Path $ShortcutPath) {
    Remove-Item $ShortcutPath -Force
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "[SUCESSO] Inicialização automática removida com sucesso!" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Cyan
} else {
    Write-Host "[AVISO] O atalho não foi encontrado na pasta Inicializar (já está desinstalado)." -ForegroundColor Yellow
}
