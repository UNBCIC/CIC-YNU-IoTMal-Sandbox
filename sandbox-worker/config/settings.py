from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    port: int
    host: str = "0.0.0.0"
    app_base_url: str
    app_limit_concurrency: Optional[int] = None
    app_backlog: int = 2048
    app_timeout_keep_alive: int = 5
    app_name: str = "sandbox-worker-1"
    data_dir: str = "./data/"
    qemu_log_path: str = "/qemu.log"
    sandbox_manager_uri: str = ""
    analysis_duration: int = 30
    post_analysis_wait: int = 30
    model_config = SettingsConfigDict(env_file=".env", extra='ignore')

app_settings = Settings()

