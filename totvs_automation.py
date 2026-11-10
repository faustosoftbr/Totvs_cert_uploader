"""
Arquivo de compatibilidade com versões anteriores.
Redireciona para o módulo otimizado totvs_tec.
"""

from totvs_tec import (
    TotvsTecUploader as TotvsCertUploader,
    TotvsTecError as TotvsAutomationError,
)
