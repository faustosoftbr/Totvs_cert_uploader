"""
Bateria de testes automatizados para o Atualizador de Certificado Digital v3.0.0.
Valida:
1. Persistência e leitura segura de variáveis de ambiente (.env).
2. Leitura, decodificação PKCS#12 e geração de Subject DN (cert_manager).
3. Formatação e persistência de telemetria de logs (logger_service).
4. Tratamento de exceção de banco de dados offline (db_service).
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
from cryptography.x509.oid import NameOID

import cert_manager
import db_service
import logger_service
import secrets_manager


class TestTotvsCertUploader(unittest.TestCase):

    def test_secrets_env_persistence(self):
        """Valida que o gerenciador de segredos lê e persiste via .env sem expor senhas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_env = Path(tmpdir) / ".env"
            data = {"TEC_USER": "teste@empresa.com", "SQL_USER": "sa"}
            secrets_manager.save_secrets(data, target_file=test_env)
            parsed = secrets_manager._parse_env_file(test_env)
            self.assertEqual(parsed.get("TEC_USER"), "teste@empresa.com")
            self.assertEqual(parsed.get("SQL_USER"), "sa")

    def test_secrets_mask(self):
        """Valida máscara de segurança das senhas no CLI."""
        sample = "MinhaSenhaSuperSecreta123"
        masked = secrets_manager.mask_secret(sample)
        self.assertTrue(masked.startswith("Mi"))
        self.assertTrue(masked.endswith("23"))
        self.assertIn("*" * (len(sample) - 4), masked)

    def test_cert_reader_and_subject_dn(self):
        """Cria um certificado PFX sintético no padrão ICP-Brasil e valida a extração completa."""
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        
        # Padrão ICP-Brasil: CN com Razao Social:CNPJ
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ICP-Brasil"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Certificado PJ A1"),
            x509.NameAttribute(NameOID.COMMON_NAME, "EMPRESA DE TESTE LTDA:12345678000199"),
        ])
        
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
            .sign(private_key, hashes.SHA256())
        )

        pfx_data = pkcs12.serialize_key_and_certificates(
            name=b"test_cert",
            key=private_key,
            cert=cert,
            cas=None,
            encryption_algorithm=BestAvailableEncryption(b"senha123"),
        )

        with tempfile.NamedTemporaryFile(suffix=".pfx", delete=False) as tmp:
            tmp.write(pfx_data)
            tmp_path = tmp.name

        try:
            info = cert_manager.read_pfx_certificate(tmp_path, "senha123")
            self.assertEqual(info.razao_social, "EMPRESA DE TESTE LTDA")
            self.assertEqual(info.cnpj_numeros, "12345678000199")
            self.assertEqual(info.cnpj_formatado, "12.345.678/0001-99")
            self.assertFalse(info.expirado)
            self.assertGreater(info.dias_restantes, 300)
            
            # Valida formatação do Subject DN para o campo [NomeCertificado] do SQL
            self.assertIn("CN=EMPRESA DE TESTE LTDA:12345678000199", info.subject_dn)
            self.assertIn("OU=Certificado PJ A1", info.subject_dn)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_logger_service_and_local_persistence(self):
        """Valida que o logger service grava mensagens localmente e em memória."""
        captured = []
        logger = logger_service.LoggerService(gui_callback=lambda m: captured.append(m))
        logger.log("Teste de mensagem de telemetria")
        self.assertTrue(len(captured) > 0)
        self.assertIn("Teste de mensagem de telemetria", captured[0])
        self.assertIn("Teste de mensagem de telemetria", logger.get_full_log())

    def test_database_service_error_handling(self):
        """Valida que quando não há banco de dados local acessível, a mensagem amigável é retornada."""
        db = db_service.DatabaseService()
        # Força servidor inexistente
        db.candidate_instances = ["servidor_inexistente_12345"]
        with self.assertRaises(db_service.DatabaseError) as ctx:
            db.consultar_loja_1()
        self.assertIn("Totvs Chef não está instalado", str(ctx.exception))

    def test_subject_dn_totvs_order(self):
        """Valida que o Subject DN é reordenado na ordem canônica do Totvs Chef (CN..., OU..., L..., S..., O..., C...)."""
        ars_raw = "C=BR, O=ICP-Brasil, ST=MS, L=CAMPO GRANDE, OU=03962883000109, OU=Secretaria da Receita Federal do Brasil - RFB, OU=RFB e-CNPJ A1, OU=videoconferencia, CN=ARS ALIMENTOS LTDA:10500271000160"
        janaina_expected = "CN=JANAINA MARIA DA SILVA LTDA:54863528000113, OU=Certificado PJ A1, OU=Presencial, OU=34367871000160, OU=AC SOLUTI Multipla v5, L=Bonito, S=MS, O=ICP-Brasil, C=BR"
        
        ars_formatted = cert_manager.format_subject_dn_totvs_order(ars_raw)
        self.assertTrue(ars_formatted.startswith("CN=ARS ALIMENTOS LTDA:10500271000160"))
        self.assertTrue(ars_formatted.endswith("C=BR"))
        self.assertIn("S=MS", ars_formatted)
        self.assertNotIn("ST=MS", ars_formatted)
        
        janaina_formatted = cert_manager.format_subject_dn_totvs_order(janaina_expected)
        self.assertEqual(janaina_formatted, janaina_expected)


if __name__ == "__main__":
    unittest.main()
