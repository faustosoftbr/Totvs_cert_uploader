"""
Automação da Plataforma Fiscal Totvs - TPF (Passo 6).
URL: https://plataformafiscal.totvs.com.br/seguranca/login

Regra de Login:
- Login gerado a partir do campo [Nome Loja] do banco de dados local [MISTERCHEFNET]:
  remove os espaços, converte todas as letras para minúsculas e adiciona '@softbr.net'.
  Exemplo: "SOFTBR INFORMATICA" -> "softbrinformatica@softbr.net"
- Senha obtida a partir das credenciais configuradas no .env (TPF_PASSWORD ou TEC_PASSWORD).
- Navegação em janela anônima normal via Playwright (launch_incognito_browser).
- Acessa /estabelecimento, localiza a empresa por CNPJ, faz upload do PFX + senha do certificado e salva.
"""

import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Callable, Optional
from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from playwright_helper import launch_incognito_browser
from secrets_manager import load_secrets

TPF_LOGIN_URL = "https://plataformafiscal.totvs.com.br/seguranca/login"
TPF_ESTABELECIMENTO_URL = "https://plataformafiscal.totvs.com.br/estabelecimento"


class TotvsTpfError(Exception):
    pass


def formatar_login_tpf(nome_loja: str) -> str:
    """
    Formata o login para a Plataforma Fiscal Totvs (TPF):
    Pega o Nome Fantasia [Nome Loja], remove os espaços,
    converte todas as letras para minúsculas e adiciona o domínio @softbr.net.

    Exemplos:
        'SOFTBR INFORMATICA' -> 'softbrinformatica@softbr.net'
        'EMPORIO MANSUR COMER' -> 'emporiomansurcomer@softbr.net'
    """
    if not nome_loja or not str(nome_loja).strip():
        raise TotvsTpfError("Nome da Loja não fornecido para gerar o login da Plataforma Fiscal.")

    # Normaliza acentuação (ex: 'SÃO' -> 'SAO')
    nfkd = unicodedata.normalize("NFKD", str(nome_loja).strip())
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))

    # Remove todos os espaços e converte para minúsculas
    login_limpo = "".join(sem_acento.split()).lower()

    # Mantém apenas caracteres válidos para identificador de e-mail
    login_limpo = re.sub(r"[^a-z0-9._-]", "", login_limpo)

    if not login_limpo:
        raise TotvsTpfError(f"Não foi possível extrair um identificador válido de login a partir de '{nome_loja}'.")

    return f"{login_limpo}@softbr.net"


class TotvsTpfUploader:
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, headless: bool = False) -> None:
        self.log_cb = log_callback or (lambda msg: None)
        self.headless = headless
        self.timeout_ms = 45000

    def log(self, message: str) -> None:
        self.log_cb(f"[TPF / PLATAFORMA FISCAL] {message}")

    def _obter_nome_loja_banco(self) -> str:
        """Tenta consultar o [Nome Loja] diretamente no banco SQL Server local."""
        try:
            from db_service import DatabaseService
            db = DatabaseService()
            loja = db.consultar_loja_1()
            db.close()
            return loja.nome_loja
        except Exception as exc:
            self.log(f"Aviso ao consultar nome da loja no banco local: {exc}")
            return ""

    def _login(self, page: Page, login_user: str, login_pass: str) -> None:
        self.log("Acessando tela de autenticação da Plataforma Fiscal...")
        page.goto(TPF_LOGIN_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
        page.wait_for_timeout(2000)

        # Se já estiver conectado (ex: redirecionado direto para dashboard/estabelecimento)
        if "seguranca/login" not in page.url.lower():
            self.log("Sessão já ativa detectada na Plataforma Fiscal!")
            return

        self.log(f"Preenchendo login do cliente: {login_user}")

        user_input = page.locator(
            "#inputLoginEmail, input[name='Email'], input[name='email'], input[name='username'], "
            "input[type='email'], input[placeholder*='e-mail' i], input[placeholder*='email' i], "
            "input[placeholder*='usuário' i]"
        ).first

        pwd_input = page.locator(
            "#inputLoginPassword, input[name='Password'], input[name='password'], "
            "input[type='password'], input[placeholder*='senha' i]"
        ).first

        user_input.wait_for(state="visible", timeout=15000)
        user_input.fill(login_user)

        pwd_input.wait_for(state="visible", timeout=5000)
        pwd_input.fill(login_pass)

        page.wait_for_timeout(500)

        entrar_btn = page.locator(
            "button[type='submit'], input[type='submit'], button:has-text('Entrar'), "
            "button:has-text('Acessar'), button.btn-entrar"
        ).first

        if entrar_btn.is_visible(timeout=5000):
            self.log("Confirmando autenticação...")
            entrar_btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)

        # Aguarda confirmação do redirecionamento pós-login
        sucesso_login = False
        for _ in range(15):
            page.wait_for_timeout(1000)
            if "seguranca/login" not in page.url.lower():
                sucesso_login = True
                break

        if not sucesso_login:
            # Tenta capturar mensagem de erro exibida na página
            erro_detalhe = ""
            try:
                alertas = page.locator(
                    ".alert-danger, .validation-summary-errors, .toast-message, span.field-validation-error, div.alert"
                ).all_inner_texts()
                textos = [a.strip() for a in alertas if a.strip()]
                if textos:
                    erro_detalhe = f" ({' | '.join(textos)})"
            except Exception:
                pass

            raise TotvsTpfError(
                f"Falha ao autenticar na Plataforma Fiscal com o usuário '{login_user}'{erro_detalhe}. "
                "Verifique se o cadastro e a senha estão corretos."
            )

        self.log("Autenticação na Plataforma Fiscal realizada com sucesso!")

    def _navigate_and_update_certificate(
        self, page: Page, cert_path: str, cert_pwd: str, cnpj: Optional[str] = None
    ) -> str:
        self.log("Navegando para o módulo de Estabelecimentos...")
        page.goto(TPF_ESTABELECIMENTO_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
        page.wait_for_timeout(2500)

        cnpj_numeros = "".join(filter(str.isdigit, cnpj)) if cnpj else ""

        # Se houver CNPJ, tenta filtrar/buscar na tabela
        if cnpj:
            self.log(f"Buscando estabelecimento correspondente ao CNPJ '{cnpj}'...")
            search_input = page.locator(
                "input[type='search'], input[placeholder*='Pesquisar' i], "
                "input[placeholder*='Buscar' i], input[name*='search' i]"
            ).first
            if search_input.is_visible(timeout=3000):
                search_input.fill(cnpj)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1500)

        self.log("Localizando opção de edição do estabelecimento (ícone de lápis)...")
        edit_clicked = False

        # Tenta localizar a linha específica do CNPJ
        if cnpj:
            cnpj_row = page.locator(f"tr:has-text('{cnpj}'), tr:has-text('{cnpj_numeros}')").first
            if cnpj_row.count() > 0:
                row_edit = cnpj_row.locator(
                    "a[href*='editar'], button[title*='Editar'], i.fa-pencil, i.fa-edit, a:has(i), button:has(i)"
                ).first
                if row_edit.is_visible(timeout=2000):
                    row_edit.click()
                    edit_clicked = True

        if not edit_clicked:
            # Seletores gerais de edição na tabela de estabelecimentos
            edit_locators = [
                "a[href*='editar'], button[title*='Editar']",
                "i.fa-pencil, i.fa-edit, i.fa-pencil-alt",
                "a:has(i[class*='pencil']), a:has(i[class*='edit'])",
                "button:has(i[class*='pencil']), button:has(i[class*='edit'])",
                "table tbody tr td a:first-child",
            ]
            for sel in edit_locators:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    edit_clicked = True
                    break

        if not edit_clicked:
            raise TotvsTpfError("Botão de edição do estabelecimento não localizado na Plataforma Fiscal.")

        page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
        page.wait_for_timeout(2000)

        self.log(f"Anexando arquivo do certificado '{Path(cert_path).name}'...")
        file_input = page.locator("input[type='file']").first
        if file_input.count() > 0:
            file_input.set_input_files(cert_path)
        else:
            select_btn = page.locator("button:has-text('Selecionar'), a:has-text('Selecionar')").first
            with page.expect_file_chooser(timeout=5000) as fc_info:
                select_btn.click()
            fc_info.value.set_files(cert_path)

        page.wait_for_timeout(800)

        # Preenche a senha do certificado digital
        self.log("Inserindo senha do certificado digital...")
        pwd_input = page.locator("input[type='password']").first
        pwd_input.wait_for(state="visible", timeout=5000)
        pwd_input.fill(cert_pwd)

        page.wait_for_timeout(800)
        self.log("Salvando alterações do certificado na Plataforma Fiscal...")
        salvar_btn = page.locator(
            "button:has-text('Salvar alterações'), button:has-text('Salvar'), input[value*='Salvar']"
        ).first
        salvar_btn.wait_for(state="visible", timeout=5000)
        salvar_btn.click()

        # Aguarda confirmação do salvamento
        page.wait_for_timeout(3000)
        return "Certificado atualizado com sucesso na Plataforma Fiscal (TPF)!"

    def run(
        self,
        cert_path: str,
        cert_password: str,
        cnpj: Optional[str] = None,
        nome_loja: Optional[str] = None,
    ) -> str:
        """
        Executa o fluxo completo do Passo 6:
        1. Gera o login a partir do [Nome Loja] (banco de dados) + @softbr.net.
        2. Inicia uma janela anônima normal do navegador.
        3. Realiza o login com a senha configurada no .env (TPF_PASSWORD ou TEC_PASSWORD).
        4. Navega até estabelecimentos e atualiza o certificado PFX.
        """
        # Se nome_loja não foi passado, tenta obter do banco local
        if not nome_loja:
            self.log("Buscando [Nome Loja] no banco de dados local...")
            nome_loja = self._obter_nome_loja_banco()

        if not nome_loja:
            raise TotvsTpfError(
                "Não foi possível identificar o [Nome Loja] para gerar o login da Plataforma Fiscal. "
                "Certifique-se de que o banco de dados SQL Server está acessível."
            )

        login_email = formatar_login_tpf(nome_loja)
        secrets = load_secrets()
        login_pass = (secrets.get("TPF_PASSWORD", "").strip() or secrets.get("TEC_PASSWORD", "").strip())
        if not login_pass:
            raise TotvsTpfError(
                "Senha da Plataforma Fiscal não informada. Defina TPF_PASSWORD ou TEC_PASSWORD no arquivo .env."
            )

        self.log(f"Login calculado a partir do Nome Loja ('{nome_loja}'): {login_email}")

        with sync_playwright() as p:
            self.log("Iniciando janela anônima normal do navegador para a Plataforma Fiscal...")
            browser, context, page = launch_incognito_browser(p, headless=self.headless)

            try:
                self._login(page, login_user=login_email, login_pass=login_pass)
                res = self._navigate_and_update_certificate(page, cert_path, cert_password, cnpj=cnpj)
                self.log("Atualização no TPF concluída com sucesso!")
                return res
            finally:
                try:
                    if page:
                        page.close()
                except Exception:
                    pass
                try:
                    if context:
                        context.close()
                except Exception:
                    pass
                try:
                    if browser:
                        browser.close()
                except Exception:
                    pass
