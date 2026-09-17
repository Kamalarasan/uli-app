from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    # NVIDIA
    NVIDIA_API_KEY: str = "nvapi-placeholder"
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_EMBED_MODEL: str = "nvidia/nv-embed-v1"
    NVIDIA_RERANKER_MODEL: str = "nvidia/reranking-mistral-4b-instruct"
    NVIDIA_SMALL_MODEL: str = "nvidia/nemotron-mini-4b-instruct"
    NVIDIA_LARGE_MODEL: str = "nvidia/llama-3.1-nemotron-70b-instruct"
    
    # Database
    DB_HOST: str = "mariadb"
    DB_PORT: int = 3306
    DB_USER: str = "uli_user"
    DB_PASS: str = "uli_password"
    DB_NAME: str = "uli_db"
    
    # App
    SECRET_KEY: str = "change-me-in-production-32chars-min"
    DEBUG: bool = False
    UPLOAD_DIR: str = "/app/uploads"
    MAX_RETRIES: int = 30
    RETRY_INTERVAL: int = 2
    
    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
