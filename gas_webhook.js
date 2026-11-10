/**
 * Google Apps Script - Webhook para Envio de Logs de Atualização de Certificado
 * 
 * Como publicar:
 * 1. Acesse https://script.google.com e crie um "Novo projeto".
 * 2. Cole este código no editor (substituindo o conteúdo de Código.gs).
 * 3. Clique em "Implantar" > "Nova implantação".
 * 4. Selecione o tipo "App da Web" (ícone de engrenagem).
 * 5. Configurações:
 *    - Descrição: Webhook Logs Softbr
 *    - Executar como: Eu (fausto.softbr@gmail.com)
 *    - Quem pode acessar: Qualquer pessoa (Anyone)
 * 6. Clique em "Implantar", autorize o acesso à sua conta Google e copie a "URL do app da Web".
 * 7. Configure a URL no aplicativo executando: python secrets_manager.py --config
 */

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return ContentService.createTextOutput(JSON.stringify({ status: "error", message: "Nenhum dado recebido" }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
    var data = JSON.parse(e.postData.contents);
    var destinatario = "fausto.softbr@gmail.com";
    var assunto = data.assunto || "LOG: Atualização de Certificado Digital";
    var corpo = data.corpo || "(Log vazio)";
    
    // Dispara o e-mail diretamente pela infraestrutura segura do Google
    GmailApp.sendEmail(destinatario, assunto, corpo);
    
    return ContentService.createTextOutput(JSON.stringify({ status: "success", message: "E-mail enviado com sucesso" }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput("Webhook de Logs da Softbr ativo.");
}
