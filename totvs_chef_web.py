"""
Automação do Totvs Chef Web Cloud (Passo 4).
URL: https://chefwebcloud.chef.totvs.com.br
Login administrativo com SOFTBR.05, localização da loja por Nome Fantasia,
navegação para Cadastros > Loja > Aba Recepção NF-e, upload do PFX e salvamento.
"""

import time
from pathlib import Path
from typing import Callable, Optional
from playwright.sync_api import FrameLocator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from playwright_helper import launch_incognito_browser
from secrets_manager import load_secrets


class TotvsChefWebError(Exception):
    pass


class TotvsChefWebUploader:
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, headless: bool = False) -> None:
        self.log_cb = log_callback or (lambda msg: None)
        self.headless = headless
        secrets = load_secrets()
        self.username = secrets.get("CHEFWEB_USER", "")
        self.password = secrets.get("CHEFWEB_PASSWORD", "")
        self.timeout_ms = 40000

    def log(self, message: str) -> None:
        self.log_cb(f"[CHEF WEB] {message}")

    def _login(self, page: Page, nome_loja: str = '') -> None:
        self.log("Acessando Chef Web Cloud...")
        base_url = "https://chefwebcloud.chef.totvs.com.br"
        page.goto(base_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        page.wait_for_timeout(2000)

        # Se já estiver autenticado (ex: redirecionado para dashboard/home)
        if "login" not in page.url.lower():
            return

        self.log("Autenticando no Chef Web Cloud...")
        user_input = page.locator("#UserName, input[name*='User'], input[name*='login'], #Usuario").first
        pwd_input = page.locator("#Senha, input[name*='Password'], input[name*='senha'], #Senha").first

        user_input.wait_for(state="visible", timeout=self.timeout_ms)
        user_input.fill(self.username)
        pwd_input.fill(self.password)

        self.log("Clicando no botão de Login...")
        login_btn = page.locator("#btnLogin, button:has-text('Login')").first
        login_btn.wait_for(state="visible", timeout=self.timeout_ms)
        login_btn.click()
        page.wait_for_timeout(2500)

        # Trata seleção de Ambiente / Domínio comparando com o [Nome Loja] do SQL
        domain_select = page.locator("#comboBoxDomain")
        if domain_select.is_visible(timeout=5000):
            self.log(f"Buscando ambiente da empresa correspondente a '{nome_loja}'...")
            options = domain_select.locator("option").all()
            target_val = None
            target_label = None
            nome_loja_clean = nome_loja.strip().upper()

            # 1. Busca exata ou por início: "<Nome Loja> - <Cod Loja>"
            for opt in options:
                opt_text = opt.inner_text().strip().upper()
                if not opt_text:
                    continue
                if opt_text.startswith(nome_loja_clean) or nome_loja_clean in opt_text:
                    target_val = opt.get_attribute("value")
                    target_label = opt.inner_text().strip()
                    break

            # 2. Busca parcial por palavras-chave se não encontrou o nome completo
            if not target_val:
                palavras = [p for p in nome_loja_clean.split() if len(p) >= 4]
                if palavras:
                    for opt in options:
                        opt_text = opt.inner_text().strip().upper()
                        if all(p in opt_text for p in palavras):
                            target_val = opt.get_attribute("value")
                            target_label = opt.inner_text().strip()
                            break

            if not target_val:
                raise TotvsChefWebError(
                    f"Ambiente da empresa correspondente a '{nome_loja}' não foi localizado na lista de domínios do Chef Web Cloud."
                )

            self.log(f"Ambiente da empresa localizado: '{target_label}'")
            page.select_option("#comboBoxDomain", value=target_val)
            page.wait_for_timeout(800)

        # Clica em Entrar no domínio
        entrar_btn = page.locator("#btnEntrar, button:has-text('Entrar')").first
        if entrar_btn.is_visible(timeout=3000):
            self.log("Confirmando entrada no ambiente da empresa...")
            entrar_btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
            page.wait_for_timeout(2500)

        if "login" in page.url.lower():
            err_el = page.locator(".alert-danger, .validation-summary-errors, .error-message, [role='alert']").first
            err_msg = err_el.inner_text().strip() if err_el.is_visible(timeout=1000) else "Credenciais recusadas."
            raise TotvsChefWebError(f"Falha de login no Chef Web: {err_msg}")

    def _select_store_and_edit(self, page: Page, nome_loja: str) -> None:
        self.log(f"Acessando página de Lojas e selecionando '{nome_loja}'...")
        loja_url = "https://chefwebcloud.chef.totvs.com.br/Cadastros/Loja"
        page.goto(loja_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        page.wait_for_timeout(3000)

        # Seleciona a linha correspondente à loja (caso haja mais de uma)
        row = page.locator(f"tr:has-text('{nome_loja}')").first
        if row.count() > 0 and row.is_visible(timeout=3000):
            self.log(f"Linha da loja '{nome_loja}' selecionada na tabela.")
            row.click()
        else:
            # Fallback para a primeira linha de dados da grid
            first_row = page.locator("table tbody tr, tr.dxgvDataRow_MetropolisBlue").first
            if first_row.is_visible(timeout=2000):
                first_row.click()
        page.wait_for_timeout(1000)

        # Clica no botão 'Editar' na barra de ferramentas
        self.log("Clicando em 'Editar' para abrir o formulário da loja...")
        vis_edit = page.locator("button#toolBarEditItem:visible, button:has-text('Editar'):visible")
        if vis_edit.count() > 0:
            vis_edit.first.click()
        else:
            page.evaluate("runInSession('editItem()')")

        page.wait_for_timeout(3000)

    def _upload_certificate_refeicao_nfe(self, page: Page, cert_path: str, cert_password: str) -> str:
        self.log("Acessando aba 'Recepção NF-e'...")
        tab_locators = [
            "a[href*='#recepcaonfe']",
            "a:has-text('Recepção NF-e')",
            "a:has-text('Recepção')",
            "#tab-recepcao-nfe",
        ]
        tab_clicked = False
        for sel in tab_locators:
            tab = page.locator(sel).first
            if tab.is_visible(timeout=2000):
                tab.click()
                tab_clicked = True
                break

        if not tab_clicked:
            page.goto("https://chefwebcloud.chef.totvs.com.br/Cadastros/Loja#recepcaonfe", wait_until="domcontentloaded")

        page.wait_for_timeout(2000)

        self.log("Abrindo formulário de inclusão do certificado (botão #btnCert)...")
        btn_cert = page.locator("#btnCert, button:has-text('Adicionar / Atualizar'), button:has-text('Adicionar/Atualizar')").first
        btn_cert.wait_for(state="visible", timeout=15000)
        btn_cert.click()
        page.wait_for_timeout(3000)

        self.log(f"Anexando certificado '{Path(cert_path).name}' e informando senha no iframe UploadCertificado...")
        # O formulário do certificado fica dentro do iframe UploadCertificado
        frame = page.frame_locator("iframe[src*='UploadCertificado']")
        
        file_input = frame.locator("#fileUpload, input[type='file']").first
        file_input.wait_for(state="attached", timeout=15000)
        file_input.set_input_files(cert_path)
        page.wait_for_timeout(1000)

        pwd_input = frame.locator("#pwd, input[type='password']").first
        pwd_input.wait_for(state="visible", timeout=10000)
        pwd_input.fill(cert_password)
        page.wait_for_timeout(1000)

        self.log("Confirmando certificado no modal (#toolbarRun)...")
        confirm_btn = frame.locator("#toolbarRun, button:has-text('Confirmar'), input[value='Confirmar']").first
        confirm_btn.click()
        page.wait_for_timeout(4000)

        self.log("Salvando configurações da Loja (#toolBarSaveItem)...")
        save_btn = page.locator("button#toolBarSaveItem:visible, button:has-text('Salvar'):visible").first
        if save_btn.count() > 0:
            save_btn.click()
        else:
            page.evaluate("runInSession('saveItem()')")

        page.wait_for_timeout(3000)
        return "Certificado atualizado com sucesso no Chef Web Cloud!"

    def run(self, nome_loja: str, cert_path: str, cert_password: str) -> str:
        with sync_playwright() as p:
            browser, context, page = launch_incognito_browser(p, headless=self.headless)
            try:
                self._login(page, nome_loja=nome_loja)
                self._select_store_and_edit(page, nome_loja)
                res = self._upload_certificate_refeicao_nfe(page, cert_path, cert_password)
                self.log("Atualização no Chef Web concluída com sucesso!")
                return res
            finally:
                try:
                    context.close()
                    browser.close()
                except Exception:
                    pass
