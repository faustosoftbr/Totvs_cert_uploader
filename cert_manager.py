"""
Módulo de gestão e processamento de certificados digitais (PKCS#12 / .pfx / .p12).
Extração de dados fiscais (CNPJ, Razão Social, RFC4514 Subject DN) e instalação no Windows Store.
"""

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtensionOID, NameOID


@dataclass
class CertificateInfo:
    file_path: str
    razao_social: str
    cnpj_numeros: str
    cnpj_formatado: str
    emissor: str
    valido_de: datetime
    valido_ate: datetime
    dias_restantes: int
    expirado: bool
    subject_dn: str  # Formato RFC 4514 / LDAP esperado pelo SQL Server [NomeCertificado]


def format_cnpj(cnpj: str) -> str:
    digits = re.sub(r"\D", "", cnpj or "")
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
    return cnpj or ""


def _extract_cnpj_from_cert(cert: x509.Certificate, cn_text: str) -> str:
    # 1. Padrão comum ICP-Brasil no Common Name: "RAZAO SOCIAL:12345678000199"
    if ":" in cn_text:
        tail = cn_text.rsplit(":", 1)[1].strip()
        digits = re.sub(r"\D", "", tail)
        if len(digits) == 14:
            return digits

    # 2. OID oficial ICP-Brasil 2.16.76.1.3.3 (CNPJ da Pessoa Jurídica) em SAN OtherName
    try:
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        for other_name in san.value.get_values_for_type(x509.OtherName):
            if other_name.type_id.dotted_string == "2.16.76.1.3.3":
                raw_bytes = other_name.value
                decoded = raw_bytes.decode("latin-1", errors="ignore")
                match = re.search(r"(\d{14})", decoded)
                if match:
                    return match.group(1)
    except Exception:
        pass

    # 3. Busca por sequência de 14 dígitos nos atributos do Subject
    for attr in cert.subject:
        val = str(attr.value)
        match = re.search(r"(?<!\d)(\d{14})(?!\d)", val)
        if match:
            return match.group(1)

    return ""


def format_subject_dn_totvs_order(dn_str: str) -> str:
    """
    Reordena qualquer string de Subject DN para a ordem canônica do Totvs Chef / Windows CryptoAPI:
    CN=..., OU=..., L=..., S=..., O=..., C=...
    Exemplo:
    'CN=JANAINA MARIA DA SILVA LTDA:54863528000113, OU=Certificado PJ A1, OU=Presencial, OU=34367871000160, OU=AC SOLUTI Multipla v5, L=Bonito, S=MS, O=ICP-Brasil, C=BR'
    """
    if not dn_str:
        return ""
    order_priority = {"CN": 1, "OU": 2, "L": 3, "S": 4, "O": 5, "C": 6}
    parts = [p.strip() for p in dn_str.split(",") if p.strip()]
    items = []
    for idx, part in enumerate(parts):
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k == "ST":
                k = "S"
            items.append((k, v, idx))
    items.sort(key=lambda x: (order_priority.get(x[0], 99), x[2]))
    return ", ".join(f"{k}={v}" for k, v, _ in items)


def _build_subject_dn(cert: x509.Certificate) -> str:
    """
    Monta a string do Subject na ordem canônica do Microsoft Windows / Totvs Chef:
    CN=..., OU=..., L=..., S=..., O=..., C=...
    Ex: CN=JANAINA MARIA DA SILVA LTDA:54863528000113, OU=Certificado PJ A1, OU=Presencial, OU=34367871000160, OU=AC SOLUTI Multipla v5, L=Bonito, S=MS, O=ICP-Brasil, C=BR
    """
    mapping = {
        "commonName": "CN",
        "organizationalUnitName": "OU",
        "localityName": "L",
        "stateOrProvinceName": "S",
        "organizationName": "O",
        "countryName": "C",
    }
    order_priority = {
        "CN": 1,
        "OU": 2,
        "L": 3,
        "S": 4,
        "O": 5,
        "C": 6,
    }

    raw_items = []
    for idx, attr in enumerate(cert.subject):
        name = attr.oid._name if hasattr(attr.oid, "_name") else attr.oid.dotted_string
        tag = mapping.get(name, name)
        if tag == "ST":
            tag = "S"
        raw_items.append((tag, str(attr.value), idx))

    sorted_items = sorted(raw_items, key=lambda item: (order_priority.get(item[0], 99), item[2]))
    return ", ".join(f"{tag}={val}" for tag, val, _ in sorted_items)


def read_pfx_certificate(file_path: str, password: str) -> CertificateInfo:
    """Lê e valida o arquivo PKCS#12 (.pfx / .p12)."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    pfx_bytes = path.read_bytes()
    pwd_bytes: Optional[bytes] = password.encode("utf-8") if password is not None else None

    try:
        private_key, cert, additional_certs = pkcs12.load_key_and_certificates(pfx_bytes, pwd_bytes)
    except ValueError as exc:
        msg = str(exc).lower()
        if any(w in msg for w in ("password", "mac", "decrypt", "pkcs12")):
            raise ValueError("Senha do certificado incorreta ou arquivo corrompido.") from exc
        raise ValueError(f"Não foi possível ler o certificado: {exc}") from exc

    if cert is None:
        raise ValueError("O arquivo informado não contém um certificado X.509 válido.")

    cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    cn_text = str(cn_attrs[0].value) if cn_attrs else "Desconhecido"

    if ":" in cn_text:
        razao_social = cn_text.rsplit(":", 1)[0].strip()
    else:
        razao_social = cn_text.strip()

    cnpj_numeros = _extract_cnpj_from_cert(cert, cn_text)
    cnpj_formatado = format_cnpj(cnpj_numeros)

    issuer_cn = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
    emissor = str(issuer_cn[0].value) if issuer_cn else cert.issuer.rfc4514_string()

    valido_de = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before.replace(tzinfo=timezone.utc)
    valido_ate = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    dias_restantes = (valido_ate - now).days
    expirado = valido_ate < now

    subject_dn = _build_subject_dn(cert)

    return CertificateInfo(
        file_path=str(path.resolve()),
        razao_social=razao_social,
        cnpj_numeros=cnpj_numeros,
        cnpj_formatado=cnpj_formatado,
        emissor=emissor,
        valido_de=valido_de,
        valido_ate=valido_ate,
        dias_restantes=dias_restantes,
        expirado=expirado,
        subject_dn=subject_dn,
    )


def install_certificate_in_windows(file_path: str, password: str, store_location: str = "Cert:\\CurrentUser\\My") -> tuple[bool, str]:
    """
    Instala o certificado .pfx no repositório de certificados do Windows (Passo 5).
    Por padrão instala em CurrentUser\\My (Pessoal) com a chave privada marcada como Exportável.
    Não requer privilégios de Administrador.
    """
    abs_path = str(Path(file_path).resolve())
    # Escapa aspas para PowerShell seguro
    safe_path = abs_path.replace("'", "''")
    safe_pwd = password.replace("'", "''")

    ps_script = (
        f"$sec = ConvertTo-SecureString '{safe_pwd}' -AsPlainText -Force; "
        f"$cert = Import-PfxCertificate -FilePath '{safe_path}' "
        f"-CertStoreLocation '{store_location}' -Exportable -Password $sec; "
        f"if ($cert) {{ Write-Output ('SUCESSO:' + $cert.Thumbprint) }} else {{ Write-Error 'Falha ao importar' }}"
    )

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            timeout=20,
        )
        output = proc.stdout.strip()
        errors = proc.stderr.strip()

        if proc.returncode == 0 and "SUCESSO:" in output:
            thumbprint = output.split("SUCESSO:")[1].strip()
            return True, f"Certificado instalado com sucesso no Windows ({store_location}). Thumbprint: {thumbprint}"
        else:
            return False, f"Falha na instalação do certificado no Windows: {errors or output}"
    except Exception as exc:
        return False, f"Erro ao executar instalação no Windows: {exc}"
