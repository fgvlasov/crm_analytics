from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "test", "staging", "production"] = "local"
    app_name: str = "leadintel"
    app_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    secret_key: str = Field(min_length=16)
    encryption_master_key: str = Field(min_length=16)
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    database_url: str = "postgresql+psycopg://leadintel:leadintel@localhost:5432/leadintel"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "leadintel-local"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"

    seed_demo: bool = True
    seed_tenant_slug: str = "coldex-demo"
    seed_tenant_name: str = "Coldex Demo"
    seed_admin_email: str = "admin@coldex-demo.example"
    seed_admin_password: str = "ChangeMeDemo123!"
    seed_admin_name: str = "Coldex Admin"

    feature_odoo_connector: bool = False
    feature_fast_ai: bool = False
    feature_deep_research: bool = False
    feature_smart_rpt: bool = False
    feature_web_news_collectors: bool = False

    @model_validator(mode="after")
    def validate_feature_dependencies(self) -> "Settings":
        if self.feature_deep_research and not self.feature_fast_ai:
            raise ValueError(
                "FEATURE_DEEP_RESEARCH requires FEATURE_FAST_AI=true"
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def feature_map(self) -> dict[str, bool]:
        return {
            "odoo_connector": self.feature_odoo_connector,
            "fast_ai": self.feature_fast_ai,
            "deep_research": self.feature_deep_research,
            "smart_rpt": self.feature_smart_rpt,
            "web_news_collectors": self.feature_web_news_collectors,
        }

    def is_feature_enabled(self, name: str) -> bool:
        return bool(self.feature_map().get(name, False))


@lru_cache
def get_settings() -> Settings:
    return Settings()
