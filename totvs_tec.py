"""
Automação do Portal TEC Totvs Hospitalidade (Passo 3).
URL: https://tec.totvshospitalidade.com/auth/login
Efetua login com credenciais de parceiro, localiza o tenant pelo CNPJ e anexa o certificado.
"""

import time
from pathlib import Path
from typing import Callable, Optional
from playwright.sync_api import FrameLocator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from playwright_helper import launch_incognito_browser
from secrets_manager import load_secrets


class TotvsTecError(Exception):
    pass


class TotvsTecUploader:
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, headless: bool = False) -> None:
        self.log_cb = log_callback or (lambda msg: None)
        self.headless = headless
        secrets = load_secrets()
        self.username = secrets.get("TEC_USER", "")
        self.password = secrets.get("TEC_PASSWORD", "")
        self.timeout_ms = 35000

    def log(self, message: str) -> None:
        self.log_cb(f"[PORTAL TEC] {message}")

    def _get_auth_frame(self, page: Page) -> FrameLocator:
        return page.frame_locator("iframe[src*='acesso.totvshospitalidade.com']")

    def _dismiss_popups(self, page: Page) -> None:
        auth_frame = self._get_auth_frame(page)
        selectors = [
            "identity-mfa-warning-modal button:has-text('Entendi')",
            "identity-mfa-warning-modal button",
            "button:has-text('Entendi')",
            "button:has-text('Fechar')",
            ".po-modal button:has-text('Entendi')",
            ".po-modal button:has-text('Fechar')",
        ]
        for sel in selectors:
            try:
                loc = auth_frame.locator(sel).first
                if loc.is_visible(timeout=200):
                    loc.click(timeout=1000)
            except Exception:
                pass
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=200):
                    loc.click(timeout=1000)
            except Exception:
                pass

    def _login(self, page: Page) -> None:
        self.log("Acessando portal TEC...")
        page.goto("https://tec.totvshospitalidade.com/", wait_until="domcontentloaded", timeout=self.timeout_ms)
        page.wait_for_timeout(3000)
        self._dismiss_popups(page)

        auth_frame = self._get_auth_frame(page)
        search_input = auth_frame.locator("input.po-search-input").first
        if search_input.is_visible(timeout=1500):
            return

        self.log("Autenticando credenciais do parceiro...")
        user_input = auth_frame.locator("input[type='text'], input[type='email']").first
        pwd_input = auth_frame.locator("input[type='password']").first

        try:
            user_input.wait_for(state="visible", timeout=self.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise TotvsTecError("Tela de login do Portal TEC não respondeu a tempo.") from exc

        self._dismiss_popups(page)
        user_input.fill(self.username)
        pwd_input.fill(self.password)

        entrar_btn = auth_frame.get_by_role("button", name="Entrar", exact=True)
        entrar_btn.click()

        deadline = time.time() + (self.timeout_ms / 1000.0)
        while time.time() < deadline:
            self._dismiss_popups(page)
            if search_input.is_visible(timeout=500):
                break
            err = auth_frame.locator(".po-toaster, .po-field-container-bottom-text-error, [role='alert']").first
            if err.is_visible(timeout=200):
                txt = (err.inner_text() or "").strip()
                if txt and any(w in txt.lower() for w in ("inválid", "incorret", "erro")):
                    raise TotvsTecError(f"Falha de autenticação no Portal TEC: {txt}")
            page.wait_for_timeout(500)
        else:
            raise TotvsTecError("Tempo esgotado aguardando carregamento do painel do Portal TEC.")

    def _search_and_enter_company(self, page: Page, cnpj_formatado: str) -> None:
        self.log(f"Localizando tenant da empresa {cnpj_formatado}...")
        auth_frame = self._get_auth_frame(page)
        search_input = auth_frame.locator("input.po-search-input").first
        search_input.wait_for(state="visible", timeout=self.timeout_ms)
        search_input.fill(cnpj_formatado)
        search_input.press("Enter")

        page.wait_for_timeout(2000)
        self._dismiss_popups(page)

        acessar_btns = auth_frame.locator("button:has-text('Acessar')")
        if acessar_btns.count() == 0:
            raise TotvsTecError(f"Empresa com CNPJ {cnpj_formatado} não localizada no Portal TEC.")

        acessar_btns.first.click()
        page.wait_for_selector(".po-menu-item", timeout=self.timeout_ms)

    def _navigate_to_upload(self, page: Page) -> None:
        self.log("Navegando para Geral > Empresa...")
        self._dismiss_popups(page)
        page.locator(".po-menu-item:has-text('Geral')").first.click()
        page.wait_for_timeout(800)
        page.locator(".po-menu-item-level-two:has-text('Empresa'), .po-menu-item:has-text('Empresa')").first.click()
        page.wait_for_timeout(1500)
        self._dismiss_popups(page)

    def _upload(self, page: Page, cert_path: str, cert_pwd: str) -> str:
        self.log("Enviando certificado...")
        enviar_btn = page.locator("button:has-text('Enviar Certificado'), button:has-text('Enviar certificado')").first
        enviar_btn.wait_for(state="visible", timeout=self.timeout_ms)
        enviar_btn.click()

        page.wait_for_timeout(1500)
        pwd_input = page.locator("input[type='password'][name='password'], input[id^='po-password'], input[type='password']").first
        pwd_input.wait_for(state="visible", timeout=10000)
        pwd_input.fill(cert_pwd)

        file_attached = False
        select_file_btn = page.locator("button:has-text('Selecionar arquivo')").first
        if select_file_btn.count() > 0 and select_file_btn.is_visible(timeout=2000):
            try:
                with page.expect_file_chooser(timeout=5000) as fc_info:
                    select_file_btn.click()
                fc_info.value.set_files(cert_path)
                file_attached = True
            except Exception:
                pass

        if not file_attached:
            file_input = page.locator("input.po-upload-input, input[type='file'][name='upload'], input[type='file']").first
            if file_input.count() > 0:
                file_input.set_input_files(cert_path)
                file_attached = True

        if not file_attached:
            raise TotvsTecError("Não foi possível anexar o arquivo .pfx no formulário.")

        page.wait_for_timeout(800)
        salvar_btn = page.get_by_role("button", name="Salvar", exact=True)
        salvar_btn.wait_for(state="visible", timeout=5000)
        salvar_btn.click()

        deadline = time.time() + 20.0
        while time.time() < deadline:
            toasts = page.locator(".po-toaster, po-toaster, .po-notification, [role='alert']")
            for i in range(toasts.count()):
                el = toasts.nth(i)
                if el.is_visible(timeout=200):
                    txt = (el.inner_text() or "").strip()
                    if txt:
                        if any(w in txt.lower() for w in ("sucesso", "salvo", "atualizado", "enviado")):
                            return txt
                        if any(w in txt.lower() for w in ("erro", "inválid", "incorret", "expirad", "divergente")):
                            raise TotvsTecError(f"Aviso do Portal TEC: {txt}")
            if "/general/company" in page.url and "/certificate" not in page.url:
                return "Certificado salvo com sucesso no Portal TEC!"
            page.wait_for_timeout(400)

        return "Certificado enviado no Portal TEC."

    def run(self, cnpj_formatado: str, cert_path: str, cert_password: str) -> str:
        with sync_playwright() as p:
            browser, context, page = launch_incognito_browser(p, headless=self.headless)
            try:
                self._login(page)
                self._search_and_enter_company(page, cnpj_formatado)
                self._navigate_to_upload(page)
                res = self._upload(page, cert_path, cert_password)
                self.log("Envio no Portal TEC concluído com sucesso!")
                return res
            finally:
                try:
                    context.close()
                    browser.close()
                except Exception:
                    pass
