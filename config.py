import os
from dataclasses import dataclass
from secrets_manager import load_secrets


@dataclass
class AppConfig:
    login_url: str = "https://tec.totvshospitalidade.com/"
    username: str = ""
    password: str = ""
    headless: bool = True
    timeout_ms: int = 30000


def load_config() -> AppConfig:
    secrets = load_secrets()
    return AppConfig(
        username=secrets.get("TEC_USER", ""),
        password=secrets.get("TEC_PASSWORD", ""),
        headless=True,
    )
