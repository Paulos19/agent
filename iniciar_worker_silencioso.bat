@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Iniciando Worker em segundo plano (sem janela preta)...
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0worker.py"
echo Worker iniciado com sucesso!
ping -n 2 127.0.0.1 >nul
