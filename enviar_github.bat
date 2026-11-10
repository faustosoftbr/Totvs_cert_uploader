@echo off
chcp 65001 >nul
title Enviar alteracoes para o GitHub
cd /d "%~dp0"

echo ======================================================================
echo           VERIFICAÇÃO DE SEGURANÇA ANTES DO PUSH (GITHUB)
echo ======================================================================

REM Verifica se arquivos proibidos estão sendo rastreados pelo git
git ls-files | findstr /i /r "^\.env$ _secrets\.py \.pfx$ \.p12$ \.key$" >nul
if %errorlevel% == 0 (
    echo.
    echo [ALERTA CRÍTICO DE SEGURANÇA]
    echo Arquivos com dados sensíveis (.env, _secrets.py ou certificados) estao rastreados no Git!
    echo O envio foi CANCELADO para proteger sua conta do GitHub contra suspensão.
    echo.
    echo Execute 'git status' e remova os arquivos do rastreamento antes de tentar novamente.
    echo ======================================================================
    pause
    exit /b 1
)

echo [OK] Nenhum arquivo sensivel rastreado no Git.
echo.
echo Enviando commits para o GitHub (branch main)...
echo Se aparecer a janela de login do GitHub, faca o login com a sua NOVA CONTA e autorize.
echo.
git push -u origin main
echo.
git status -sb
pause
