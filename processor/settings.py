"""
v3 配置中心：全量外置(.env)，pydantic-settings 读取。
processor / server / im 共用此处的 get_settings() 单例。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- LLM / Embedding(DashScope, OpenAI 兼容) ----
    openai_api_key: str = ""
    openai_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_default_model: str = "qwen-plus"
    llm_default_temperature: float = 0.1
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024

    # ---- PostgreSQL(文本元数据) ----
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "xiaosu"
    postgres_password: str = "xiaosu_dev_pw"
    postgres_db: str = "xiaosu"

    # ---- MinIO(原文件存储) ----
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "xiaosu"
    minio_secret_key: str = "xiaosu_dev_pw"
    minio_bucket: str = "xiaosu-files"
    minio_secure: bool = False

    # ---- 向量库(进程内 Chroma / numpy 兜底) ----
    vector_store: str = "chroma"  # chroma | numpy
    chroma_path: str = "data/chroma"

    # ---- 钉钉 Stream ----
    dingtalk_app_key: str = ""
    dingtalk_app_secret: str = ""

    # ---- 服务 ----
    backend_port: int = 8000
    mock_port: int = 8001
    log_dir: str = "logs"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"user={self.postgres_user} password={self.postgres_password} dbname={self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
