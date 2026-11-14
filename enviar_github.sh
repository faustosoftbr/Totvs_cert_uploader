#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "======================================================================"
echo "          VERIFICAÇÃO DE SEGURANÇA ANTES DO PUSH (GITHUB)"
echo "======================================================================"

FORBIDDEN=$(git ls-files | grep -E "^\.env$|_secrets\.py|\.pfx$|\.p12$|\.key$" || true)
if [ -n "$FORBIDDEN" ]; then
    echo ""
    echo "[ALERTA CRÍTICO DE SEGURANÇA]"
    echo "Arquivos com dados sensíveis (.env, _secrets.py ou certificados) estão rastreados no Git:"
    echo "$FORBIDDEN"
    echo "O envio foi CANCELADO para proteger sua conta do GitHub contra suspensão."
    echo ""
    echo "Execute 'git status' e remova os arquivos do rastreamento antes de tentar novamente."
    echo "======================================================================"
    exit 1
fi

echo "[OK] Nenhum arquivo sensível rastreado no Git."
echo ""
echo "Enviando commits para o GitHub (branch main)..."
echo ""
git push -u origin main
echo ""
git status -sb
