"""
Gerenciamento seguro de credenciais e configurações internas da Softbr.
Lê as configurações a partir do arquivo .env ou variáveis de ambiente.
NENHUMA SENHA DEVE SER COMMITADA OU HARDCODED NESTE ARQUIVO.
"""

import os
import sys
from pathlib import Path


def _get_project_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
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
    "TPF_USER": "",
    "TPF_PASSWORD": "",
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


def load_secrets() -> dict[str, str]:
    """Carrega as credenciais a partir do arquivo .env ou variáveis de ambiente."""
    secrets = dict(DEFAULT_SECRETS)

    # 1. Tenta carregar do .env no diretório do projeto ou no diretório atual
    env_paths = [
        ENV_FILE,
        Path.cwd() / ".env",
    ]
    for p in env_paths:
        if p.is_file():
            loaded = _parse_env_file(p)
            for k, v in loaded.items():
                if v:
                    secrets[k] = v
            break

    # 2. Variáveis de ambiente têm precedência se definidas
    for k in DEFAULT_SECRETS:
        env_val = os.environ.get(k)
        if env_val:
            secrets[k] = env_val

    # 3. Fallback legado para _secrets.py local (se existir e não estiver em .env)
    try:
        import _secrets
        if hasattr(_secrets, "ENC_SECRETS"):
            import base64
            key = bytes([0x5A, 0x3C, 0x7F, 0x19, 0xA2, 0x4D, 0x88, 0xE1])
            for k, enc_val in _secrets.ENC_SECRETS.items():
                if not secrets.get(k):
                    try:
                        raw = bytes(b ^ key[i % len(key)] for i, b in enumerate(base64.b64decode(enc_val)))
                        secrets[k] = raw.decode("utf-8")
                    except Exception:
                        pass
    except Exception:
        pass

    return secrets


def save_secrets(secrets_dict: dict[str, str], target_file: Path | None = None) -> None:
    """Salva as credenciais no arquivo .env local (ignorado pelo git)."""
    target = target_file or ENV_FILE
    lines = [
        "# Configurações locais da aplicação - NUNCA ENVIE ESTE ARQUIVO AO GITHUB",
        "# Para compartilhar com a equipe, use o modelo .env.example",
        "",
    ]
    for k, v in secrets_dict.items():
        lines.append(f"{k}={v}")
    lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")


def mask_secret(value: str) -> str:
    if not value:
        return "(vazio)"
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + ("*" * (len(value) - 4)) + value[-2:]


def cli_interactive_prompt() -> None:
    """Prompt interativo para consultar e alterar senhas da aplicação."""
    print("=" * 60)
    print("      SOFTBR - GERENCIADOR DE SENHAS E INTEGRAÇÕES")
    print("=" * 60)
    
    current = load_secrets()
    labels = {
        "TEC_USER": "Portal TEC - Usuário",
        "TEC_PASSWORD": "Portal TEC - Senha",
        "CHEFWEB_USER": "Chef Web Cloud - Usuário",
        "CHEFWEB_PASSWORD": "Chef Web Cloud - Senha",
        "SQL_USER": "SQL Server - Usuário (sa)",
        "SQL_PASSWORD": "SQL Server - Senha (sa)",
        "GAS_WEBHOOK_URL": "Webhook Google Apps Script (Envio de Logs)",
        "TPF_USER": "Plataforma Fiscal TPF - Usuário (opcional)",
        "TPF_PASSWORD": "Plataforma Fiscal TPF - Senha (opcional)",
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
        print("  [1-9] Alterar credencial correspondente")
        print("  [V]   Visualizar credenciais sem máscara")
        print("  [S]   Salvar no .env local e Sair")
        print("  [Q]   Sair sem salvar")

        choice = input("\nEscolha uma opção: ").strip().upper()

        if choice == "S":
            save_secrets(current)
            print(f"\nCredenciais salvas com sucesso em: {ENV_FILE}")
            break
        elif choice == "Q":
            print("\nOperação cancelada.")
            break
        elif choice == "V":
            print("\n--- Credenciais sem máscara ---")
            for key in keys:
                print(f"{labels[key]}: {current.get(key, '')}")
            input("\nPressione [Enter] para continuar...")
        elif choice.isdigit() and 1 <= int(choice) <= len(keys):
            target_key = keys[int(choice) - 1]
            print(f"\nValor atual de {labels[target_key]}: {current.get(target_key, '')}")
            new_val = input(f"Novo valor para {labels[target_key]} (ou Enter para manter): ").strip()
            if new_val != "":
                current[target_key] = new_val
                print(f"-> {labels[target_key]} atualizado na memória. (Lembre-se de teclar 'S' para salvar)")
        else:
            print("Opção inválida. Tente novamente.")


if __name__ == "__main__":
    cli_interactive_prompt()
