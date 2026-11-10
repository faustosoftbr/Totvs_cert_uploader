@echo off
chcp 65001 >nul
title Teste Isolado Passo 6 - Plataforma Fiscal TPF
cd /d "%~dp0"

echo ==============================================================
echo    Iniciando Teste Isolado do Passo 6 (TPF - Plataforma Fiscal)
echo ==============================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" testar_passo_6_tpf.py
) else (
    python testar_passo_6_tpf.py
)

pause
