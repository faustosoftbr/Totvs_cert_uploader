# TOTVS Cert Uploader (NFe / NFCe)

Aplicativo Desktop em Python (`CustomTkinter` + `Playwright` + `cryptography` + `pyodbc`) para leitura, validação local, atualização no banco SQL Server local (MISTERCHEFNET), envio aos portais TOTVS (Portal TEC, Chef Web Cloud e TPF), instalação no repositório de certificados do Windows e telemetria de logs via Webhook.

---

## Por que um aplicativo executável e não um site na nuvem?

Por regras de segurança (*sandbox* e políticas de segurança dos navegadores modernos), uma página web remota (hospedada em `https://seusite.com.br`) não consegue:

- **Conectar via TCP na porta 1433 do `localhost`** para consultar e atualizar o banco de dados SQL Server local (`localhost\SQLEXPRESS`).
- **Acessar credenciais salvas e sessões de cookies** do navegador padrão do cliente para plataformas fiscais locais.
- **Chamar comandos do sistema operacional** (como `powershell` / `certutil`) para instalar o certificado digital diretamente no repositório de certificados do Windows (`Cert:\CurrentUser\My`) com a chave privada marcada como exportável.

### A Solução Executável:
Em vez de depender de um site remoto limitado, o cliente recebe um executável único e seguro (`TOTVS-Cert-Uploader.exe`). Ele executa com permissões normais de usuário do Windows, acessa a base local do Totvs Chef, realiza as automações necessárias de ponta a ponta e entrega uma interface visual moderna, simples e intuitiva para usuários leigos.

---

## Versões Disponíveis

| Versão | Descrição |
| :--- | :--- |
| **`v1.0.0`** | Versão inicial com campos manuais de login e senha do Portal TEC. |
| **`v2.0.0`** | Versão para cliente final com credenciais embutidas e upload exclusivo no Portal TEC. |
| **`v3.0.0`** | **Pipeline Completo Integrado**: <br>1. Validação local do PFX (CNPJ, Razão Social, Validade e Subject DN).<br>2. Consulta e atualização do SQL Server local (`[MISTERCHEFNET].[dbo].[Lojas]`).<br>3. Upload no Portal TEC (Totvs Hospitalidade).<br>4. Upload no Chef Web Cloud (localizando a loja pelo Nome Fantasia).<br>5. Instalação do certificado no repositório do Windows como Exportável.<br>6. Upload na Plataforma Fiscal TPF (caso utilize módulo NFe).<br>7. Solicitação opcional de reinicialização do Windows.<br>8. Telemetria e envio de logs por e-mail via Google Apps Script Webhook. |

---

## Arquitetura e Módulos do Sistema

- `app.py`: Interface gráfica CustomTkinter e orquestração do pipeline em thread desacoplada.
- `cert_manager.py`: Extração e validação de certificados PKCS#12 e rotinas de instalação no Windows Store.
- `db_service.py`: Camada de comunicação com o SQL Server local (Loja 1 e detecção de NFe).
- `totvs_tec.py`: Automação Playwright em segundo plano para o Portal TEC.
- `totvs_chef_web.py`: Automação Playwright para o Chef Web Cloud.
- `totvs_tpf.py`: Automação Playwright para a Plataforma Fiscal Totvs (TPF).
- `logger_service.py`: Log em tempo real, persistência em arquivo e despacho via Webhook.
- `secrets_manager.py`: Gerenciamento seguro de credenciais locais via `.env` (ignorado pelo Git) e CLI interativa para consulta/alteração.
- `gas_webhook.js`: Script do Google Apps Script para disparo seguro de e-mails via GmailApp.

---

## Manutenção de Senhas e Credenciais (Segurança)

As credenciais do sistema ficam armazenadas localmente no arquivo `.env` (ignorado pelo `.gitignore`) e **nunca** são enviadas ao repositório GitHub.

Para configurar em um novo ambiente:
1. Copie o modelo `.env.example` para `.env`:
   ```bash
   copy .env.example .env
   ```
2. Para consultar ou alterar as senhas de forma interativa e mascarada:
   ```bash
   python secrets_manager.py
   ```

O comando exibirá o menu interativo para visualizar (mascarado ou sem máscara) e atualizar credenciais do Portal TEC, Chef Web Cloud, Plataforma Fiscal TPF, SQL Server e Webhook de Logs, persistindo diretamente no arquivo local `.env`.
