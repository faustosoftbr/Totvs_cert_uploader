"""
Módulo de logs e telemetria.
Exibe informações em tempo real na interface gráfica, salva em arquivo local
e envia o relatório consolidado por e-mail via Google Apps Script Webhook.
"""

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
import requests

from secrets_manager import load_secrets

LOG_FILE = Path("atualizacao_cert.log")


class LoggerService:
    def __init__(self, gui_callback: Optional[Callable[[str], None]] = None) -> None:
        self.gui_cb = gui_callback or (lambda msg: None)
        self.lines: list[str] = []
        secrets = load_secrets()
        self.webhook_url = secrets.get("GAS_WEBHOOK_URL", "").strip()

    def log(self, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{ts}] {message}"
        self.lines.append(formatted)
        self.gui_cb(formatted)

        # Salva incrementalmente no arquivo local
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
        except Exception:
            pass

    def get_full_log(self) -> str:
        return "\n".join(self.lines)

    def dispatch_email(self, empresa_identificador: str) -> bool:
        """
        Dispara o log consolidado para o Google Apps Script Webhook.
        O script do Google Apps envia o e-mail para fausto.softbr@gmail.com
        com o assunto: 'LOG: <nome da empresa no SQL>'.
        """
        if not self.webhook_url:
            self.log("[TELEMETRIA] Webhook do Google Apps Script não configurado. Envio de e-mail ignorado.")
            return False

        subject = f"LOG: {empresa_identificador or 'Empresa Não Identificada'}"
        body = (
            f"Relatório de Execução - Atualizador de Certificado Softbr\n"
            f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"Empresa: {empresa_identificador}\n"
            f"{'=' * 60}\n\n"
            f"{self.get_full_log()}\n"
        )

        try:
            self.log("[TELEMETRIA] Transmitindo log consolidado para envio por e-mail...")
            resp = requests.post(
                self.webhook_url,
                json={"assunto": subject, "corpo": body},
                headers={"Content-Type": "application/json"},
                timeout=12,
            )
            if resp.status_code == 200:
                try:
                    res_data = resp.json()
                    if res_data.get("status") == "success":
                        self.log("[TELEMETRIA] Log enviado com sucesso por e-mail via Webhook!")
                        return True
                    else:
                        msg = res_data.get("message", resp.text[:200])
                        self.log(f"[TELEMETRIA] Webhook retornou erro: {msg}")
                        return False
                except Exception:
                    if "doPost" in resp.text:
                        self.log("[TELEMETRIA] Erro no Google Apps Script: Função doPost não foi encontrada na implantação.")
                    else:
                        self.log(f"[TELEMETRIA] Webhook retornou resposta inesperada (não-JSON): {resp.text[:120]}")
                    return False
            else:
                self.log(f"[TELEMETRIA] Servidor de logs retornou status {resp.status_code}: {resp.text}")
                return False
        except Exception as exc:
            self.log(f"[TELEMETRIA] Aviso: Não foi possível transmitir o e-mail de log: {exc}")
            return False
