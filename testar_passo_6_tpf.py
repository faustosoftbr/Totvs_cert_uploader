"""
Script de Teste Isolado do Passo 6 - Plataforma Fiscal Totvs (TPF).
Executa única e exclusivamente o Passo 6, mantendo os Passos 1 a 5 intocados.
Abre a janela anônima normal do navegador para acompanhamento em tempo real.
"""

import os
import sys
from pathlib import Path

# Adiciona diretório raiz ao path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from cert_manager import read_pfx_certificate
from totvs_tpf import TotvsTpfError, TotvsTpfUploader, formatar_login_tpf

DEFAULT_CERT = r"C:\Users\Haroldo\Meu Drive\Clientes\00 Certificados\EMPORIO MANSUR COMER - SENHA 123456 val10.2027.pfx"
DEFAULT_PWD = "123456"


def main():
    print("=" * 70)
    print("   TESTE ISOLADO: PASSO 6 - PLATAFORMA FISCAL TOTVS (TPF)")
    print("=" * 70)

    cert_path = DEFAULT_CERT
    cert_pwd = DEFAULT_PWD

    if not os.path.isfile(cert_path):
        print(f"\n[AVISO] Certificado padrão não encontrado em:\n  {cert_path}")
        cert_path = input("\nInforme o caminho completo do arquivo .pfx: ").strip(' "\'')
        cert_pwd = input("Informe a senha do certificado: ").strip()

    if not os.path.isfile(cert_path):
        print(f"[ERRO] Arquivo não localizado: {cert_path}")
        return

    print(f"\nLendo certificado: {Path(cert_path).name}...")
    try:
        cert_info = read_pfx_certificate(cert_path, cert_pwd)
        print(f"  Razão Social : {cert_info.razao_social}")
        print(f"  CNPJ         : {cert_info.cnpj_formatado}")
        print(f"  Validade     : {cert_info.valido_ate.strftime('%d/%m/%Y')}")
    except Exception as e:
        print(f"[ERRO] Falha ao ler certificado: {e}")
        return

    # Tenta consultar o [Nome Loja] no banco local
    nome_loja = None
    try:
        from db_service import DatabaseService
        db = DatabaseService()
        loja = db.consultar_loja_1()
        db.close()
        nome_loja = loja.nome_loja
        print(f"  Nome Loja    : {nome_loja} (obtido do banco [MISTERCHEFNET])")
    except Exception as exc:
        print(f"  [AVISO] Banco local inacessível ({exc}).")
        resp = input("\nInforme o [Nome Loja] (ou ENTER para 'SOFTBR INFORMATICA'): ").strip()
        nome_loja = resp if resp else "SOFTBR INFORMATICA"

    login_esperado = formatar_login_tpf(nome_loja)
    print(f"  Login TPF    : {login_esperado}")
    print("  Senha TPF    : (definida no .env)")

    print("\nIniciando navegador em janela anônima para o Passo 6 (TPF)...")
    print("Você poderá acompanhar todas as ações diretamente na tela.\n")

    def logger(msg: str):
        print(f"  {msg}")

    uploader = TotvsTpfUploader(log_callback=logger, headless=False)

    try:
        res = uploader.run(
            cert_path=cert_path,
            cert_password=cert_pwd,
            cnpj=cert_info.cnpj_formatado,
            nome_loja=nome_loja,
        )
        print("\n" + "=" * 70)
        print(f"SUCESSO NO PASSO 6: {res}")
        print("=" * 70)
    except TotvsTpfError as e:
        print("\n" + "!" * 70)
        print(f"ERRO NO PASSO 6 (TPF): {e}")
        print("!" * 70)
    except Exception as e:
        print("\n" + "!" * 70)
        print(f"ERRO INESPERADO NO PASSO 6: {e}")
        print("!" * 70)


if __name__ == "__main__":
    try:
        main()
    finally:
        print("\n" + "-" * 70)
        input("Pressione ENTER para encerrar este teste...")
