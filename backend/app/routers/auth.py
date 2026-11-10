from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.errors import AppError
from app.schemas import AuthOut, LoginIn, ProfileUpdate, RegisterIn, UserOut
from app.security import (
    create_local_token,
    decode_local_token,
    hash_password,
    verify_cognito_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
_bearer = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def _user_out(user: dict) -> UserOut:
    return UserOut(**{key: user[key] for key in ("id", "email", "name", "campus", "bio", "created_at")})


def _user_from_access_token(request: Request, token: str | None) -> dict:
    settings = request.app.state.settings
    if not token:
        raise AppError("Sign in required.", 401)
    repo = request.app.state.repo
    if settings.auth_mode == "local":
        user_id = decode_local_token(token, settings.jwt_secret)
        user = repo.get_user_by_id(user_id)
        if not user:
            raise AppError("Sign in required.", 401)
        return user
    if settings.auth_mode == "cognito":
        identity = verify_cognito_token(
            token,
            region=settings.cognito_region,
            user_pool_id=settings.cognito_user_pool_id,
            app_client_id=settings.cognito_app_client_id,
        )
        return repo.upsert_identity(
            user_id=identity["id"],
            email=identity["email"],
            name=identity["name"],
        )
    raise AppError(f"Unknown auth mode: {settings.auth_mode}", 503)


def require_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> dict:
    token = credentials.credentials if credentials else None
    return _user_from_access_token(request, token)


def optional_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> dict | None:
    if credentials is None:
        return None
    return _user_from_access_token(request, credentials.credentials)


@router.post("/register", response_model=AuthOut, status_code=201)
def register(body: RegisterIn, request: Request):
    settings = request.app.state.settings
    if settings.auth_mode != "local":
        raise AppError(
            "This server uses Amazon Cognito. Create the account in the user pool. Local registration is disabled.",
            400,
        )
    repo = request.app.state.repo
    if repo.get_user_by_email(str(body.email)):
        raise AppError("An account with that email already exists.", 409)
    user = repo.create_user(
        email=str(body.email),
        name=body.name,
        password_hash=hash_password(body.password),
        campus=body.campus,
    )
    token = create_local_token(user["id"], settings.jwt_secret, settings.jwt_expire_minutes)
    return AuthOut(access_token=token, auth_mode="local", user=_user_out(user))


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, request: Request):
    settings = request.app.state.settings
    if settings.auth_mode != "local":
        raise AppError(
            "This server uses Amazon Cognito. Sign in with the Cognito user pool. Local password login is disabled.",
            400,
        )
    repo = request.app.state.repo
    record = repo.get_user_by_email(str(body.email))
    if not record or not verify_password(body.password, record.get("password_hash")):
        raise AppError("Email or password is incorrect.", 401)
    user = repo.get_user_by_id(record["id"])
    token = create_local_token(user["id"], settings.jwt_secret, settings.jwt_expire_minutes)
    return AuthOut(access_token=token, auth_mode="local", user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(request: Request, user: Annotated[dict, Depends(require_user)]):
    del request
    return _user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, request: Request, user: Annotated[dict, Depends(require_user)]):
    changes = body.model_dump(exclude_unset=True)
    updated = request.app.state.repo.update_user(user["id"], changes)
    return _user_out(updated)
