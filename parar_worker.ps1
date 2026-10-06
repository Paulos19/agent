$procs = Get-CimInstance Win32_Process | Where-Object { ($_.Name -like 'python*.exe') -and ($_.CommandLine -like '*worker*') }
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Encerrando processos do Worker Local..." -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
if ($procs) {
    foreach ($p in $procs) {
        Stop-Process -Id $p.ProcessId -Force
        Write-Host "[PARADO] Processo PID $($p.ProcessId) ($($p.Name)) encerrado." -ForegroundColor Yellow
    }
} else {
    Write-Host "[AVISO] Nenhum worker.py em execução no momento." -ForegroundColor Cyan
}
