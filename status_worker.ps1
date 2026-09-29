$procs = Get-CimInstance Win32_Process | Where-Object { ($_.Name -like 'python*.exe') -and ($_.CommandLine -like '*worker.py*') }
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Status do Worker Local" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
if ($procs) {
    Write-Host "[STATUS]: EM EXECUÇÃO (Ativo na VPS)" -ForegroundColor Green
    foreach ($p in $procs) {
        Write-Host "  • PID: $($p.ProcessId) | Executável: $($p.Name)"
    }
} else {
    Write-Host "[STATUS]: PARADO (Inativo)" -ForegroundColor Red
}

Write-Host ""
Write-Host "--- Últimas 15 linhas do worker.log ---" -ForegroundColor Cyan
$logPath = Join-Path $PSScriptRoot "worker.log"
if (Test-Path $logPath) {
    Get-Content $logPath -Tail 15
} else {
    Write-Host "Arquivo worker.log ainda não foi gerado."
}
