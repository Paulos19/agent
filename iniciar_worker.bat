@echo off
title Assistente Local Worker - PC Pessoal
echo ========================================================
echo   Iniciando Assistente Worker no Computador Pessoal
echo ========================================================
echo.
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe worker.py
) else (
    python worker.py
)
pause
