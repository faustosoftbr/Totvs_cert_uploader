"""
Aplicativo Desktop para Atualização de Certificado Digital - Softbr (v3.0.0).
Interface gráfica nativa intuitiva em CustomTkinter com execução dos Passos 1 a 7 em segundo plano.
"""

import threading
import tkinter.messagebox as msgbox
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

from cert_manager import CertificateInfo, format_cnpj, format_subject_dn_totvs_order, install_certificate_in_windows, read_pfx_certificate
from db_service import DatabaseError, DatabaseService
from logger_service import LoggerService
from reboot_service import reiniciar_computador_windows
from totvs_chef_web import TotvsChefWebError, TotvsChefWebUploader
from totvs_tec import TotvsTecError, TotvsTecUploader

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_VERSION = "3.0.0"


class CertUploaderApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Atualizador de Certificado Digital - Softbr v{APP_VERSION}")
        self.geometry("860x680")
        self.minsize(780, 600)

        self.cert_info: Optional[CertificateInfo] = None
        self.is_running: bool = False
        self.logger = LoggerService(gui_callback=self._append_log)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._build_header()
        self._build_cert_card()
        self._build_details_card()
        self._build_status_and_actions()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(16, 6), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text=f"Atualizador de Certificado Digital Softbr (v{APP_VERSION})",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = ctk.CTkLabel(
            header,
            text="Selecione o arquivo do certificado (.pfx ou .p12), informe a senha e clique em 'INICIAR ATUALIZAÇÃO'.",
            font=ctk.CTkFont(size=13),
            text_color="#A0AEC0",
            anchor="w",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _build_cert_card(self) -> None:
        card = ctk.CTkFrame(self, corner_radius=10)
        card.grid(row=1, column=0, padx=20, pady=8, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        section_lbl = ctk.CTkLabel(
            card,
            text="1. Arquivo e Senha do Certificado Digital",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        section_lbl.grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 8), sticky="w")

        ctk.CTkLabel(card, text="Arquivo (.pfx/.p12):").grid(row=1, column=0, padx=(16, 8), pady=6, sticky="w")
        self.file_entry = ctk.CTkEntry(card, placeholder_text="Clique em 'Selecionar Arquivo...' para localizar o certificado")
        self.file_entry.grid(row=1, column=1, columnspan=2, padx=4, pady=6, sticky="ew")

        self.browse_btn = ctk.CTkButton(card, text="Selecionar Arquivo...", width=160, command=self._on_browse_file)
        self.browse_btn.grid(row=1, column=3, padx=(8, 16), pady=6)

        ctk.CTkLabel(card, text="Senha do Certificado:").grid(row=2, column=0, padx=(16, 8), pady=(6, 14), sticky="w")
        self.cert_pwd_entry = ctk.CTkEntry(card, placeholder_text="Digite a senha do certificado digital...", show="•")
        self.cert_pwd_entry.grid(row=2, column=1, padx=4, pady=(6, 14), sticky="ew")
        self.cert_pwd_entry.bind("<Return>", lambda _e: self._validate_certificate())
        self.cert_pwd_entry.bind("<FocusOut>", lambda _e: self._auto_validate_if_ready())

        self.show_pwd_var = ctk.BooleanVar(value=False)
        self.show_pwd_cb = ctk.CTkCheckBox(
            card,
            text="Mostrar senha",
            variable=self.show_pwd_var,
            command=self._toggle_cert_password,
            width=110,
        )
        self.show_pwd_cb.grid(row=2, column=2, padx=8, pady=(6, 14))

        self.validate_btn = ctk.CTkButton(
            card,
            text="Validar Certificado",
            width=160,
            fg_color="#2B6CB0",
            hover_color="#2C5282",
            command=self._validate_certificate,
        )
        self.validate_btn.grid(row=2, column=3, padx=(8, 16), pady=(6, 14))

    def _build_details_card(self) -> None:
        card = ctk.CTkFrame(self, corner_radius=10)
        card.grid(row=2, column=0, padx=20, pady=8, sticky="ew")
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(3, weight=1)

        section_lbl = ctk.CTkLabel(
            card,
            text="2. Dados Identificados no Certificado",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        section_lbl.grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 8), sticky="w")

        ctk.CTkLabel(card, text="Razão Social:").grid(row=1, column=0, padx=(16, 8), pady=4, sticky="w")
        self.razao_lbl = ctk.CTkLabel(card, text="—", font=ctk.CTkFont(weight="bold"), anchor="w")
        self.razao_lbl.grid(row=1, column=1, columnspan=3, padx=4, pady=4, sticky="ew")

        ctk.CTkLabel(card, text="CNPJ da Empresa:").grid(row=2, column=0, padx=(16, 8), pady=4, sticky="w")
        self.cnpj_entry = ctk.CTkEntry(card, placeholder_text="00.000.000/0000-00", state="disabled")
        self.cnpj_entry.grid(row=2, column=1, padx=4, pady=4, sticky="ew")

        ctk.CTkLabel(card, text="Validade:").grid(row=2, column=2, padx=(16, 8), pady=4, sticky="w")
        self.validade_lbl = ctk.CTkLabel(card, text="—", anchor="w")
        self.validade_lbl.grid(row=2, column=3, padx=(4, 16), pady=4, sticky="ew")

    def _build_status_and_actions(self) -> None:
        container = ctk.CTkFrame(self, corner_radius=10)
        container.grid(row=3, column=0, padx=20, pady=(8, 16), sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(3, weight=1)

        # Banner de Aviso de Sucesso / Erro no painel
        self.status_banner = ctk.CTkFrame(container, corner_radius=8, fg_color="#2D3748")
        self.status_banner.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew")
        self.status_banner.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self.status_banner,
            text="Status: Aguardando seleção e validação do certificado digital.",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#E2E8F0",
            wraplength=760,
            justify="left",
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, padx=14, pady=10, sticky="ew")

        # Barra de progresso
        self.progress_bar = ctk.CTkProgressBar(container, mode="determinate", height=10)
        self.progress_bar.grid(row=1, column=0, padx=16, pady=(2, 6), sticky="ew")
        self.progress_bar.set(0)

        # Botão principal de Envio
        self.start_btn = ctk.CTkButton(
            container,
            text="INICIAR ATUALIZAÇÃO DO CERTIFICADO",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2F855A",
            hover_color="#276749",
            command=self._on_start_process,
        )
        self.start_btn.grid(row=2, column=0, padx=16, pady=6, sticky="ew")

        # Histórico de progresso
        self.log_box = ctk.CTkTextbox(container, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.grid(row=3, column=0, padx=16, pady=(6, 14), sticky="nsew")
        self.log_box.configure(state="disabled")
        self._append_log("Pronto. Selecione o arquivo .pfx ou .p12 e informe a senha.")

    def _toggle_cert_password(self) -> None:
        self.cert_pwd_entry.configure(show="" if self.show_pwd_var.get() else "•")

    def _set_cnpj_value(self, value: str) -> None:
        self.cnpj_entry.configure(state="normal")
        self.cnpj_entry.delete(0, "end")
        self.cnpj_entry.insert(0, value)
        self.cnpj_entry.configure(state="disabled")

    def _append_log(self, formatted_line: str) -> None:
        def _update() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", formatted_line + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, _update)

    def _set_banner(self, text: str, level: str = "info") -> None:
        colors = {
            "info": ("#2D3748", "#E2E8F0"),
            "working": ("#2B6CB0", "#FFFFFF"),
            "success": ("#22543D", "#C6F6D5"),
            "warning": ("#744210", "#FEFCBF"),
            "error": ("#742A2A", "#FED7D7"),
        }
        bg, fg = colors.get(level, colors["info"])

        def _update() -> None:
            self.status_banner.configure(fg_color=bg)
            self.status_label.configure(text=text, text_color=fg)

        self.after(0, _update)

    def _set_progress(self, val: float) -> None:
        self.after(0, lambda: self.progress_bar.set(val))

    def _on_browse_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Selecionar Certificado Digital",
            filetypes=[("Certificado Digital PKCS#12", "*.pfx *.p12"), ("Todos os arquivos", "*.*")],
        )
        if file_path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, file_path)
            self.logger.log(f"Arquivo selecionado: {Path(file_path).name}")
            self._auto_validate_if_ready()

    def _auto_validate_if_ready(self) -> None:
        if self.file_entry.get().strip() and self.cert_pwd_entry.get():
            self._validate_certificate()

    def _validate_certificate(self) -> bool:
        file_path = self.file_entry.get().strip()
        cert_pwd = self.cert_pwd_entry.get()

        if not file_path:
            self._set_banner("Atenção: Selecione o arquivo .pfx ou .p12 do certificado.", "warning")
            return False
        if not cert_pwd:
            self._set_banner("Atenção: Digite a senha do certificado digital.", "warning")
            return False

        try:
            info = read_pfx_certificate(file_path, cert_pwd)
            self.cert_info = info
            self.razao_lbl.configure(text=info.razao_social)

            if info.cnpj_formatado:
                self._set_cnpj_value(info.cnpj_formatado)

            val_str = f"{info.valido_ate.strftime('%d/%m/%Y')} ({info.dias_restantes} dias restantes)"
            if info.expirado:
                self.validade_lbl.configure(text=f"EXPIRADO em {info.valido_ate.strftime('%d/%m/%Y')}", text_color="#FC8181")
                self._set_banner(
                    f"Atenção: O certificado de '{info.razao_social}' está EXPIRADO ({info.valido_ate.strftime('%d/%m/%Y')})!",
                    "error",
                )
            else:
                color = "#68D391" if info.dias_restantes > 30 else "#F6E05E"
                self.validade_lbl.configure(text=val_str, text_color=color)
                self._set_banner(
                    f"Certificado validado: {info.razao_social} | CNPJ: {info.cnpj_formatado or 'Não identificado'}",
                    "success",
                )

            self.logger.log(
                f"Certificado validado: {info.razao_social} | CNPJ: {info.cnpj_formatado} | Válido até: {info.valido_ate.strftime('%d/%m/%Y')}"
            )
            return True
        except Exception as exc:
            self.cert_info = None
            self.razao_lbl.configure(text="—")
            self.validade_lbl.configure(text="—", text_color="#E2E8F0")
            self._set_banner(f"Erro na validação do certificado: {exc}", "error")
            self.logger.log(f"Erro ao validar certificado: {exc}")
            return False

    def _on_start_process(self) -> None:
        if self.is_running:
            return

        if not self._validate_certificate():
            return

        self.is_running = True
        self.start_btn.configure(state="disabled", text="ATUALIZANDO CERTIFICADOS EM SEGUNDO PLANO... AGUARDE")
        self._set_progress(0.05)

        thread = threading.Thread(target=self._worker_pipeline, daemon=True)
        thread.start()

    def _worker_pipeline(self) -> None:
        cert = self.cert_info
        if not cert:
            self.is_running = False
            return

        cert_path = cert.file_path
        cert_pwd = self.cert_pwd_entry.get()
        empresa_identificador = cert.cnpj_formatado or cert.razao_social

        db_service = DatabaseService()
        try:
            # -------------------------------------------------------------
            # PASSO 2: Consultar e Atualizar SQL Server local (Loja 1)
            # -------------------------------------------------------------
            self._set_banner("Passo 2/5: Conectando ao SQL Server e consultando Loja 1...", "working")
            self.logger.log("[PASSO 2] Conectando ao banco de dados MISTERCHEFNET...")
            loja = db_service.consultar_loja_1()
            empresa_identificador = f"{loja.nome_loja} ({loja.cnpj})"
            self.logger.log(f"[PASSO 2] Loja 1 identificada no SQL: Nome: '{loja.nome_loja}', CNPJ: '{loja.cnpj}'")

            # Validação do CNPJ: na versão 3.0.0 de testes, apenas registra se houver divergência
            cnpj_sql_limpo = loja.cnpj.replace(".", "").replace("/", "").replace("-", "")
            if cert.cnpj_numeros and cnpj_sql_limpo and cert.cnpj_numeros != cnpj_sql_limpo:
                self.logger.log(
                    f"[AVISO v3.0.0] Divergência entre CNPJ do certificado ({cert.cnpj_numeros}) "
                    f"e CNPJ do banco ({cnpj_sql_limpo}). Prosseguindo para validação técnica..."
                )

            # Verifica se utiliza módulo NFe
            usa_nfe = db_service.verificar_licenca_nfe()
            self.logger.log(f"[PASSO 2] Verificação de módulo NFe (últimos 60 dias): {'SIM (Ativo)' if usa_nfe else 'NÃO (Apenas NFCe)'}")

            # Atualiza o campo [NomeCertificado] com o Subject DN na ordem canônica do Totvs Chef
            subject_formatado = format_subject_dn_totvs_order(cert.subject_dn)
            self.logger.log(f"[PASSO 2] Atualizando [NomeCertificado] da Loja 1 para: {subject_formatado}")
            db_service.atualizar_certificado_loja_1(subject_formatado)
            self.logger.log("[PASSO 2] Banco de dados SQL Server atualizado com sucesso!")
            self._set_progress(0.25)

            # -------------------------------------------------------------
            # PASSO 3: Atualizar Portal TEC (Totvs Hospitalidade)
            # -------------------------------------------------------------
            self._set_banner("Passo 3/5: Enviando certificado para o Portal TEC...", "working")
            self.logger.log("[PASSO 3] Iniciando automação no Portal TEC...")
            tec_uploader = TotvsTecUploader(log_callback=self.logger.log, headless=False)
            target_cnpj = cert.cnpj_formatado or format_cnpj(cert.cnpj_numeros) or loja.cnpj
            self.logger.log(f"[PASSO 3] Buscando empresa no Portal TEC pelo CNPJ do certificado: {target_cnpj}")
            tec_res = tec_uploader.run(cnpj_formatado=format_cnpj(target_cnpj), cert_path=cert_path, cert_password=cert_pwd)
            self.logger.log(f"[PASSO 3] Resultado Portal TEC: {tec_res}")
            self._set_progress(0.45)

            # -------------------------------------------------------------
            # PASSO 4: Atualizar Chef Web Cloud
            # -------------------------------------------------------------
            self._set_banner("Passo 4/5: Atualizando certificado no Chef Web Cloud...", "working")
            self.logger.log(f"[PASSO 4] Iniciando automação no Chef Web Cloud para '{loja.nome_loja}'...")
            chef_uploader = TotvsChefWebUploader(log_callback=self.logger.log, headless=False)
            chef_res = chef_uploader.run(nome_loja=loja.nome_loja, cert_path=cert_path, cert_password=cert_pwd)
            self.logger.log(f"[PASSO 4] Resultado Chef Web: {chef_res}")
            self._set_progress(0.65)

            # -------------------------------------------------------------
            # PASSO 5: Instalar Certificado Digital no Windows
            # -------------------------------------------------------------
            self._set_banner("Passo 5/5: Instalando certificado no repositório do Windows...", "working")
            self.logger.log("[PASSO 5] Instalando certificado no Windows (CurrentUser\\My) com chave exportável...")
            ok_win, win_msg = install_certificate_in_windows(cert_path, cert_pwd)
            self.logger.log(f"[PASSO 5] {win_msg}")
            if not ok_win:
                self.logger.log("[PASSO 5] Aviso: Não foi possível registrar no Windows Store, mas prosseguindo.")
            self._set_progress(0.80)

            # -------------------------------------------------------------
            # Finalização com Sucesso e Lembrete TPF
            # -------------------------------------------------------------
            self._set_banner("SUCESSO: Certificado digital atualizado nas plataformas!", "success")
            self.logger.log("=" * 60)
            self.logger.log("PROCESSO DE ATUALIZAÇÃO CONCLUÍDO COM ÊXITO!")
            self.logger.log("=" * 60)
            if usa_nfe:
                self.logger.log("[LEMBRETE OBRIGATÓRIO - NF-e / PLATAFORMA FISCAL TPF]")
                self.logger.log("Identificada emissão ativa de NF-e nesta loja nos últimos 60 dias.")
                self.logger.log("ATENÇÃO: O certificado digital deve ser atualizado MANUALMENTE")
                self.logger.log("na Plataforma Fiscal TOTVS (TPF) pelo portal:")
                self.logger.log("   URL: https://plataformafiscal.totvs.com.br/estabelecimento")
            else:
                self.logger.log("[LEMBRETE FISCAL - PLATAFORMA FISCAL TPF]")
                self.logger.log("Caso esta loja utilize NF-e em outros módulos ou contingência,")
                self.logger.log("lembre-se de atualizar o certificado manualmente pelo portal:")
                self.logger.log("   URL: https://plataformafiscal.totvs.com.br/estabelecimento")
            self.logger.log("=" * 60)
            self._set_progress(1.0)

            # Envia telemetria por e-mail via Webhook (contendo o lembrete no log)
            self.logger.dispatch_email(loja.nome_loja)

            # Diálogo de reinicialização do Windows
            self.after(500, lambda: self._prompt_reboot(usa_nfe=usa_nfe))

        except DatabaseError as dberr:
            self._set_banner(f"ERRO DE BANCO: {dberr}", "error")
            self.logger.log(f"[ERRO FATAL BANCO] {dberr}")
            self.logger.dispatch_email(empresa_identificador)
        except (TotvsTecError, TotvsChefWebError) as autoerr:
            self._set_banner(f"ERRO NA PLATAFORMA: {autoerr}", "error")
            self.logger.log(f"[ERRO FATAL AUTOMAÇÃO] {autoerr}")
            self.logger.dispatch_email(empresa_identificador)
        except Exception as exc:
            self._set_banner(f"ERRO INESPERADO: {exc}", "error")
            self.logger.log(f"[ERRO INESPERADO] {exc}")
            self.logger.dispatch_email(empresa_identificador)
        finally:
            db_service.close()
            self.is_running = False
            self.after(0, lambda: self.start_btn.configure(state="normal", text="INICIAR ATUALIZAÇÃO DO CERTIFICADO"))

    def _prompt_reboot(self, usa_nfe: bool = False) -> None:
        """Diálogo perguntando se o cliente deseja reiniciar o computador agora."""
        aviso_tpf = (
            "\n\n[LEMBRETE IMPORTANTE]:\nComo esta loja possui emissão de NF-e, "
            "lembre-se de atualizar o certificado MANUALMENTE na Plataforma Fiscal TOTVS:\n"
            "https://plataformafiscal.totvs.com.br/estabelecimento"
            if usa_nfe
            else ""
        )
        resposta = msgbox.askyesno(
            "Reiniciar Computador",
            "A atualização do certificado digital foi concluída com sucesso!\n\n"
            "Para que todas as alterações tenham efeito no sistema fiscal, "
            "é recomendável reiniciar o computador."
            f"{aviso_tpf}\n\n"
            "Deseja reiniciar o computador agora?",
        )
        if resposta:
            self.logger.log("[REINICIALIZAÇÃO] Reinicialização autorizada pelo cliente. Reiniciando Windows em 5 segundos...")
            ok, msg = reiniciar_computador_windows(delay_segundos=5)
            self.logger.log(f"[REINICIALIZAÇÃO] {msg}")
        else:
            self.logger.log("[REINICIALIZAÇÃO] Cliente optou por reiniciar mais tarde. Concluído sem reiniciar.")


if __name__ == "__main__":
    app = CertUploaderApp()
    app.mainloop()
