"""
Módulo de comunicação com o banco de dados SQL Server local (MISTERCHEFNET).
Executa consultas de loja, verificação de movimentação fiscal (NFe) e atualização do certificado.
"""

from dataclasses import dataclass
from typing import Optional
import pyodbc

from secrets_manager import load_secrets


@dataclass
class LojaInfo:
    codigo_loja: int
    nome_loja: str
    cnpj: str
    razao_social: str
    nome_certificado: Optional[str]


class DatabaseError(Exception):
    pass


class DatabaseService:
    def __init__(self) -> None:
        secrets = load_secrets()
        self.user = secrets.get("SQL_USER", "sa")
        self.password = secrets.get("SQL_PASSWORD", "")
        self.database = "MISTERCHEFNET"
        self._conn: Optional[pyodbc.Connection] = None

    def _get_installed_odbc_drivers(self) -> list[str]:
        drivers = pyodbc.drivers()
        preferred = [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "SQL Server Native Client 11.0",
            "SQL Server",
        ]
        return [d for d in preferred if d in drivers] or drivers

    def conectar(self) -> pyodbc.Connection:
        """Tenta conectar ao SQL Server local testando instâncias conhecidas com timeout otimizado."""
        if self._conn:
            try:
                self._conn.cursor().execute("SELECT 1")
                return self._conn
            except Exception:
                self._conn = None

        candidate_instances = getattr(self, "candidate_instances", None) or [
            r"localhost\SQLEXPRESS",
            r"127.0.0.1\SQLEXPRESS",
            r"(local)",
            r"localhost",
        ]
        drivers = self._get_installed_odbc_drivers()
        if not drivers:
            raise DatabaseError("Nenhum driver ODBC do SQL Server encontrado no Windows.")

        # Utiliza o driver mais moderno disponível
        primary_driver = drivers[0]
        last_error = ""

        for server in candidate_instances:
            conn_str = (
                f"DRIVER={{{primary_driver}}};"
                f"SERVER={server};"
                f"DATABASE={self.database};"
                f"UID={self.user};"
                f"PWD={self.password};"
                f"TrustServerCertificate=yes;"
                f"Connection Timeout=3;"
            )
            try:
                conn = pyodbc.connect(conn_str, timeout=3)
                self._conn = conn
                return conn
            except Exception as exc:
                last_error = str(exc)

        # Se falhou com o driver primário e houver outros drivers instalados, faz uma tentativa com o genérico
        if len(drivers) > 1:
            for fallback_driver in drivers[1:2]:
                for server in candidate_instances[:2]:
                    conn_str = (
                        f"DRIVER={{{fallback_driver}}};"
                        f"SERVER={server};"
                        f"DATABASE={self.database};"
                        f"UID={self.user};"
                        f"PWD={self.password};"
                        f"TrustServerCertificate=yes;"
                        f"Connection Timeout=3;"
                    )
                    try:
                        conn = pyodbc.connect(conn_str, timeout=3)
                        self._conn = conn
                        return conn
                    except Exception as exc:
                        last_error = str(exc)

        raise DatabaseError(
            "Detectei que o Totvs Chef não está instalado neste computador "
            f"ou o banco de dados [MISTERCHEFNET] não está acessível no SQL Server local.\nDetalhe: {last_error}"
        )

    def consultar_loja_1(self) -> LojaInfo:
        """Consulta as informações cadastrais da Loja 1 no banco MISTERCHEFNET."""
        conn = self.conectar()
        query = """
            SELECT [Código Loja], [Nome Loja], [CNPJ], [Razão Social], [NomeCertificado]
            FROM [MISTERCHEFNET].[dbo].[Lojas]
            WHERE [Código Loja] = 1;
        """
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            if not row:
                raise DatabaseError("Loja 1 não encontrada no banco [MISTERCHEFNET].")

            return LojaInfo(
                codigo_loja=int(row[0]),
                nome_loja=str(row[1] or "").strip(),
                cnpj=str(row[2] or "").strip(),
                razao_social=str(row[3] or "").strip(),
                nome_certificado=str(row[4] or "").strip() if row[4] else None,
            )
        except Exception as exc:
            if isinstance(exc, DatabaseError):
                raise
            raise DatabaseError(f"Erro ao consultar Loja 1 no SQL Server: {exc}")

    def verificar_licenca_nfe(self) -> bool:
        """
        Verifica se existem registros fiscais de NFe nos últimos 60 dias.
        Retorna True se usa módulo NFe (deve executar passos 6 e 7), False caso contrário.
        """
        conn = self.conectar()
        query = """
            SELECT 
                CAST(
                    CASE 
                        WHEN EXISTS (
                            SELECT 1 
                            FROM [MISTERCHEFNET].[dbo].[NFe_Item]
                            WHERE [DataHoraOperacao] >= DATEADD(day, -60, GETDATE())
                        ) THEN 1
                        ELSE 0
                    END AS BIT
                ) AS [PossuiRegistros];
        """
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            if row and row[0]:
                return bool(row[0])
            return False
        except Exception:
            # Se a tabela NFe_Item não existir ou ocorrer erro, assume sem NFe
            return False

    def atualizar_certificado_loja_1(self, subject_dn: str) -> None:
        """Atualiza o campo [NomeCertificado] da Loja 1 no banco de dados."""
        conn = self.conectar()
        query = """
            UPDATE [MISTERCHEFNET].[dbo].[Lojas]
            SET [NomeCertificado] = ?
            WHERE [Código Loja] = 1;
        """
        try:
            cursor = conn.cursor()
            cursor.execute(query, (subject_dn,))
            conn.commit()
        except Exception as exc:
            raise DatabaseError(f"Erro ao atualizar [NomeCertificado] no SQL Server: {exc}")

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
