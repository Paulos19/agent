@echo off
chcp 65001 >nul
title Assistente DevOps - Local Worker
cd /d "%~dp0"
echo ========================================================
echo   Iniciando Worker em modo Visual (com terminal)
echo ========================================================
echo Para encerrar, pressione Ctrl+C ou feche esta janela.
echo.
"%~dp0.venv\Scripts\python.exe" "%~dp0worker.py"
pause
