"""Runtime configuration.

Local defaults never call AWS. An AWS backend is used only when its setting is
explicitly selected. The application does not substitute a local result when
that call fails.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always backend/.env, independent of the process working directory.
_BACKEND_ENV = Path(__file__).resolve().parents[1] / ".env"

AppMode = Literal["local", "aws"]
AuthMode = Literal["local", "cognito"]
DatabaseBackend = Literal["sqlite", "dynamodb"]
StorageBackend = Literal["local", "s3"]
DescriptionProvider = Literal["local", "bedrock"]
CategoryProvider = Literal["local", "sagemaker"]
NotificationBackend = Literal["local", "aws"]
DEFAULT_LOCAL_JWT_SECRET = "local-dev-only-change-me-use-a-private-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_BACKEND_ENV), extra="ignore")

    app_mode: AppMode = "local"
    auth_mode: AuthMode = "local"
    database_backend: DatabaseBackend = "sqlite"
    storage_backend: StorageBackend = "local"
    description_provider: DescriptionProvider = "local"
    category_provider: CategoryProvider = "local"
    notification_backend: NotificationBackend = "local"

    jwt_secret: str = DEFAULT_LOCAL_JWT_SECRET
    jwt_expire_minutes: int = 720
    sqlite_path: str = "data/campusconnect.db"
    upload_dir: str = "data/uploads"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    aws_region: str = "us-east-1"
    aws_profile: str = ""
    dynamodb_table: str = ""
    s3_bucket: str = ""
    sqs_queue_url: str = ""
    sns_topic_arn: str = ""
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""
    cognito_region: str = "us-east-1"
    bedrock_model_id: str = "us.amazon.nova-micro-v1:0"
    bedrock_max_tokens: int = Field(default=256, ge=32, le=1024)
    sagemaker_endpoint_name: str = ""

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def configuration_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.auth_mode == "local":
            if self.jwt_secret == DEFAULT_LOCAL_JWT_SECRET:
                warnings.append("Using the default local-development JWT secret.")
            if len(self.jwt_secret.encode("utf-8")) < 32:
                warnings.append("JWT_SECRET should be at least 32 bytes for HS256.")
        if self.database_backend == "dynamodb" and not self.dynamodb_table:
            warnings.append("DATABASE_BACKEND=dynamodb but DYNAMODB_TABLE is empty.")
        if self.storage_backend == "s3" and not self.s3_bucket:
            warnings.append("STORAGE_BACKEND=s3 but S3_BUCKET is empty.")
        if self.notification_backend == "aws" and (not self.sqs_queue_url or not self.sns_topic_arn):
            warnings.append("NOTIFICATION_BACKEND=aws requires SQS_QUEUE_URL and SNS_TOPIC_ARN.")
        if self.category_provider == "sagemaker" and not self.sagemaker_endpoint_name:
            warnings.append("CATEGORY_PROVIDER=sagemaker but SAGEMAKER_ENDPOINT_NAME is empty.")
        if self.auth_mode == "cognito" and (
            not self.cognito_user_pool_id or not self.cognito_app_client_id
        ):
            warnings.append("AUTH_MODE=cognito requires the user pool id and app client id.")
        mixed = []
        if self.database_backend == "dynamodb" and self.app_mode == "local":
            mixed.append("database")
        if self.storage_backend == "s3" and self.app_mode == "local":
            mixed.append("storage")
        if self.notification_backend == "aws" and self.app_mode == "local":
            mixed.append("notifications")
        if self.description_provider == "bedrock" and self.app_mode == "local":
            mixed.append("descriptions")
        if self.category_provider == "sagemaker" and self.app_mode == "local":
            mixed.append("categories")
        if self.auth_mode == "cognito" and self.app_mode == "local":
            mixed.append("authentication")
        if mixed:
            warnings.append(
                "APP_MODE=local but these integrations will make real AWS calls: " + ", ".join(mixed) + "."
            )
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()
