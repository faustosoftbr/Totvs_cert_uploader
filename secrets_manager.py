"""
Gerenciador de Credenciais e Segredos do Projeto.
Armazena e recupera credenciais em arquivo .env na raiz do projeto.
Fornece interface interativa por linha de comando (CLI) para consulta e alteração.
"""

import os
from pathlib import Path
from typing import Optional


def _get_project_dir() -> Path:
    return Path(__file__).resolve().parent


ENV_FILE = _get_project_dir() / ".env"


# Valores padrão para novos ambientes (sem senhas em texto puro)
DEFAULT_SECRETS = {
    "TEC_USER": "",
    "TEC_PASSWORD": "",
    "CHEFWEB_USER": "",
    "CHEFWEB_PASSWORD": "",
    "SQL_USER": "sa",
    "SQL_PASSWORD": "",
    "GAS_WEBHOOK_URL": "",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    """Lê um arquivo .env simples sem depender de bibliotecas externas."""
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    try:
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                result[k] = v
    except Exception:
        pass
    return result


def _write_env_file(path: Path, secrets: dict[str, str]) -> None:
    """Grava as variáveis de ambiente no formato .env padronizado."""
    lines = [
        "# Arquivo de configuracao de credenciais do Atualizador TOTVS Cert",
        "# Mantenha este arquivo seguro e nao compartilhe publicamente.",
        "",
    ]
    for k, v in secrets.items():
        lines.append(f"{k}={v}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def load_secrets() -> dict[str, str]:
    """
    Carrega as credenciais a partir do arquivo .env.
    Se alguma chave não estiver definida, utiliza os valores padrão.
    """
    data = DEFAULT_SECRETS.copy()
    if ENV_FILE.is_file():
        env_data = _parse_env_file(ENV_FILE)
        data.update(env_data)
    # Permite sobrescrita por variáveis de ambiente do sistema operacional se existirem
    for k in data.keys():
        if k in os.environ and os.environ[k].strip():
            data[k] = os.environ[k].strip()
    return data


def save_secrets(secrets: dict[str, str], target_file: Optional[Path] = None) -> None:
    """Salva o dicionário de segredos no arquivo .env local."""
    dest = target_file or ENV_FILE
    _write_env_file(dest, secrets)


def mask_secret(value: str) -> str:
    """Retorna uma versão mascarada da senha para exibição segura na tela."""
    if not value:
        return "<não configurada>"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


def interactive_cli() -> None:
    """Interface CLI interativa para consulta e alteração das senhas."""
    print("=" * 70)
    print("   GERENCIADOR DE CREDENCIAIS - ATUALIZADOR TOTVS CERT (SOFTBR)")
    print("=" * 70)
    print(f"Arquivo de destino: {ENV_FILE}")
    
    current = load_secrets()
    labels = {
        "TEC_USER": "Portal TEC - Usuário",
        "TEC_PASSWORD": "Portal TEC - Senha",
        "CHEFWEB_USER": "Chef Web Cloud - Usuário",
        "CHEFWEB_PASSWORD": "Chef Web Cloud - Senha",
        "SQL_USER": "SQL Server - Usuário (sa)",
        "SQL_PASSWORD": "SQL Server - Senha (sa)",
        "GAS_WEBHOOK_URL": "Webhook Google Apps Script (Envio de Logs)",
    }

    while True:
        print("\nConfigurações e credenciais atuais (.env):")
        keys = list(labels.keys())
        for idx, key in enumerate(keys, 1):
            val = current.get(key, "")
            is_pwd = "PASSWORD" in key or "WEBHOOK" in key
            display = mask_secret(val) if is_pwd else val
            print(f"  [{idx}] {labels[key]}: {display}")

        print("\nOpções:")
        print("  [1-7] Alterar credencial correspondente")
        print("  [V]   Visualizar credenciais sem máscara")
        print("  [S]   Salvar no .env local e Sair")
        print("  [Q]   Sair sem salvar")

        choice = input("\nEscolha uma opção: ").strip().upper()

        if choice == "S":
            save_secrets(current)
            print(f"\nCredenciais salvas com sucesso em: {ENV_FILE}")
            break
        elif choice == "Q":
            print("\nOperação cancelada. Nenhuma alteração foi gravada.")
            break
        elif choice == "V":
            print("\n--- CREDENCIAIS EM TEXTO PURO ---")
            for idx, key in enumerate(keys, 1):
                print(f"  [{idx}] {labels[key]}: {current.get(key, '')}")
            input("\nPressione ENTER para continuar...")
        elif choice.isdigit() and 1 <= int(choice) <= len(keys):
            selected_key = keys[int(choice) - 1]
            label = labels[selected_key]
            current_val = current.get(selected_key, "")
            print(f"\nAlterando: {label}")
            print(f"Valor atual: {mask_secret(current_val)}")
            new_val = input("Digite o novo valor (ou ENTER para manter o atual): ").strip()
            if new_val:
                current[selected_key] = new_val
                print(f"-> {label} atualizado!")
            else:
                print("-> Valor mantido inalterado.")
        else:
            print("Opção inválida! Escolha entre 1 e 7, ou V, S, Q.")


if __name__ == "__main__":
    interactive_cli()
