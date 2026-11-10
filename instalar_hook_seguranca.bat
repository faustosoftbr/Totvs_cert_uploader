@echo off
chcp 65001 >nul
title Instalação do Hook de Segurança Pré-Commit

echo Instalando proteção pré-commit contra envio de senhas ao GitHub...

if not exist ".git\hooks" (
    echo [ERRO] Pasta .git\hooks não encontrada. Execute na raiz do repositório Git.
    pause
    exit /b 1
)

(
echo #!/bin/sh
echo echo "==> Executando verificacao de seguranca pre-commit..."
echo FORBIDDEN_FILES=$^(git diff --cached --name-only --diff-filter=ACM ^| grep -E "^(\.env|\.env\.(local^|production^|test^|dev^)|_secrets\.py|config\.json|.*\.pfx|.*\.p12|.*\.pem|.*\.key|.*\.cer|.*\.crt)$"^|
echo if [ -n "$FORBIDDEN_FILES" ]; then
echo     echo "======================================================================"
echo     echo "[ERRO DE SEGURANCA] Arquivo sensivel detectado no commit:"
echo     echo "$FORBIDDEN_FILES"
echo     echo "Arquivos .env, _secrets.py ou certificados NUNCA devem ir para o Git."
echo     echo "Commit CANCELADO."
echo     echo "======================================================================"
echo     exit 1
echo fi
echo SUSPECT_PATTERNS="Eqepechs1\*|Douglas50@@"
echo LEAKED_LINES=$^(git diff --cached -U0 ^| grep -E "^\+" ^| grep -v "^\+\+\+" ^| grep -E "$SUSPECT_PATTERNS"^|
echo if [ -n "$LEAKED_LINES" ]; then
echo     echo "======================================================================"
echo     echo "[ERRO DE SEGURANCA] Senha detectada no codigo staged:"
echo     echo "$LEAKED_LINES"
echo     echo "Commit CANCELADO."
echo     echo "======================================================================"
echo     exit 1
echo fi
echo echo "==> Verificacao concluida com sucesso: nenhum segredo detectado."
echo exit 0
) > .git\hooks\pre-commit

echo.
echo [SUCESSO] Hook pré-commit instalado e ativo com sucesso!
echo A partir de agora, qualquer commit contendo .env, .pfx ou senhas será bloqueado automaticamente.
pause
