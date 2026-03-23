from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    port: int
    host: str = "0.0.0.0"
    app_base_url: str
    app_limit_concurrency: Optional[int] = None
    app_backlog: int = 2048
    app_timeout_keep_alive: int = 5
    app_name: str = "sandbox-manager"
    mongo_host: str = "localhost:27017"
    mongo_username: str
    mongo_password: str
    mongo_db: str = "sandbox"
    malware_directory: str
    output_dir: str = "./output/"
    upload_dir: str = "./uploads/"
    model_config = SettingsConfigDict(env_file=".env", extra='ignore')


app_settings = Settings()
