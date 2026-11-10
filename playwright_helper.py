"""
Utilitários comuns de suporte à automação Playwright.
Suprime janelas espúrias de console do driver no Windows e fornece inicializadores de navegador.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
from playwright.sync_api import Browser, BrowserContext, Page, Playwright

# Evita que o driver node.exe pisque janelas de console no Windows
if sys.platform == "win32":
    _orig_popen = subprocess.Popen

    class _NoWindowPopen(_orig_popen):
        def __init__(self, *args, **kwargs):
            if "creationflags" not in kwargs:
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                kwargs["creationflags"] |= subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    subprocess.Popen = _NoWindowPopen  # type: ignore[misc]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def launch_incognito_browser(p: Playwright, headless: bool = True) -> tuple[Browser, BrowserContext, Page]:
    """Cria uma instância anônima e limpa do Chromium (Chrome ou Edge)."""
    launch_args = [
        "--incognito",
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
    ]
    browser = None
    for channel in ("chrome", "msedge"):
        try:
            browser = p.chromium.launch(channel=channel, headless=headless, args=launch_args)
            break
        except Exception:
            continue

    if browser is None:
        browser = p.chromium.launch(headless=headless, args=launch_args)

    context = browser.new_context(
        user_agent=DEFAULT_USER_AGENT,
        viewport={"width": 1366, "height": 768},
    )
    page = context.new_page()
    return browser, context, page


def find_browser_user_data_dir() -> Optional[str]:
    """Localiza o diretório de perfil padrão do Chrome ou Edge do usuário do Windows."""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return None

    candidates = [
        Path(local_app_data) / "Google" / "Chrome" / "User Data",
        Path(local_app_data) / "Microsoft" / "Edge" / "User Data",
    ]
    for c in candidates:
        if c.is_dir():
            return str(c)
    return None
