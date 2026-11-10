@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Gerando executavel unico para o cliente final (dist\TOTVS-Cert-Uploader.exe)...
".venv\Scripts\pyinstaller.exe" --noconfirm --clean TOTVS-Cert-Uploader.spec
echo.
if exist "dist\TOTVS-Cert-Uploader.exe" (
    echo ======================================================================
    echo SUCESSO! Executavel gerado em: dist\TOTVS-Cert-Uploader.exe
    echo ======================================================================
) else (
    echo ======================================================================
    echo ERRO na geracao do executavel!
    echo ======================================================================
)
pause
