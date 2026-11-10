from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.constants import CATEGORIES, INTENTS


def _clean_category(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned not in CATEGORIES:
        allowed = ", ".join(CATEGORIES)
        raise ValueError(f"Category must be one of: {allowed}.")
    return cleaned


def _clean_intent(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned not in INTENTS:
        allowed = ", ".join(INTENTS)
        raise ValueError(f"Intent must be one of: {allowed}.")
    return cleaned


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    campus: str = Field(default="", max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    campus: str
    bio: str
    created_at: datetime


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    auth_mode: str
    user: UserOut


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    campus: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=500)


class ListingIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=4000)
    category: str
    intent: str = "offer"
    location: str = Field(default="", max_length=200)
    contact: str = Field(default="", max_length=200)
    image_key: str | None = None
    description_source: str = Field(default="user", max_length=80)
    category_source: str = Field(default="user", max_length=80)

    @field_validator("category")
    @classmethod
    def category_allowed(cls, value: str) -> str:
        return _clean_category(value)

    @field_validator("intent")
    @classmethod
    def intent_allowed(cls, value: str) -> str:
        return _clean_intent(value)


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, min_length=10, max_length=4000)
    category: str | None = None
    intent: str | None = None
    location: str | None = Field(default=None, max_length=200)
    contact: str | None = Field(default=None, max_length=200)
    status: Literal["open", "resolved"] | None = None
    image_key: str | None = None
    clear_image: bool = False
    description_source: str | None = Field(default=None, max_length=80)
    category_source: str | None = Field(default=None, max_length=80)

    @field_validator("category")
    @classmethod
    def category_allowed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_category(value)

    @field_validator("intent")
    @classmethod
    def intent_allowed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_intent(value)


class ListingOut(BaseModel):
    id: str
    owner_id: str
    owner_name: str
    title: str
    description: str
    category: str
    intent: str
    location: str
    contact: str
    image_key: str | None
    image_url: str | None
    status: str
    description_source: str
    category_source: str
    created_at: datetime
    updated_at: datetime


class ListingCreateOut(BaseModel):
    listing: ListingOut
    notification_warning: str | None = None


class DescriptionIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    category: str
    details: str = Field(default="", max_length=2000)

    @field_validator("category")
    @classmethod
    def category_allowed(cls, value: str) -> str:
        return _clean_category(value)


class DescriptionOut(BaseModel):
    description: str
    provider: str
    model_id: str | None = None
    notice: str


class CategoryIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    details: str = Field(default="", max_length=2000)


class CategoryOut(BaseModel):
    category: str
    confidence: float
    provider: str
    endpoint_name: str | None = None
    notice: str


class UploadOut(BaseModel):
    image_key: str
    image_url: str


class NotificationOut(BaseModel):
    id: str
    user_id: str
    message: str
    channel: str
    read: bool
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    service: str
    app_mode: str
    auth_mode: str
    database_backend: str
    storage_backend: str
    description_provider: str
    category_provider: str
    notification_backend: str
    warnings: list[str]
