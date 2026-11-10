"""
Serviço de reinicialização do sistema operacional Windows (Passo 7).
Executa shutdown do Windows caso o cliente aprove a reinicialização imediata.
"""

import os
import subprocess


def reiniciar_computador_windows(delay_segundos: int = 5) -> tuple[bool, str]:
    """Agenda/executa a reinicialização imediata do Windows."""
    try:
        cmd = ["shutdown.exe", "/r", "/t", str(delay_segundos), "/c", "Atualizacao de Certificado Digital Concluida."]
        res = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if res.returncode == 0:
            return True, f"O computador será reiniciado em {delay_segundos} segundos."
        return False, f"Não foi possível agendar a reinicialização: {res.stderr or res.stdout}"
    except Exception as exc:
        return False, f"Erro ao solicitar reinicialização: {exc}"
