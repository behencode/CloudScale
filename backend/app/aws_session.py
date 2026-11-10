"""Boto3 session helpers. Clients are created only by AWS-mode factories."""

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings
from app.errors import ProviderError


def aws_config() -> Config:
    return Config(
        retries={"max_attempts": 5, "mode": "adaptive"},
        connect_timeout=5,
        read_timeout=20,
    )


def aws_session(settings: Settings) -> boto3.Session:
    profile = settings.aws_profile or None
    return boto3.Session(profile_name=profile, region_name=settings.aws_region)


def provider_error(service: str, exc: Exception) -> ProviderError:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        message = exc.response.get("Error", {}).get("Message", str(exc))
        return ProviderError(f"{service} request failed: {code}: {message}")
    if isinstance(exc, BotoCoreError):
        return ProviderError(f"{service} request failed: {exc}")
    return ProviderError(f"{service} request failed: {exc}")
