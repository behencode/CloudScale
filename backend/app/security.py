"""Local password hashing and JWT helpers.

Amazon Cognito is the authentication authority when AUTH_MODE=cognito.
PBKDF2 below is only the local development mechanism.
"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.errors import AppError, ConfigurationError

LOCAL_ISSUER = "campusconnect-local"
PBKDF2_ROUNDS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algorithm, rounds, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(rounds),
        )
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_local_token(user_id: str, secret: str, expire_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iss": LOCAL_ISSUER,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_local_token(token: str, secret: str) -> str:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer=LOCAL_ISSUER,
            options={"require": ["exp", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise AppError("Sign in required.", 401) from exc
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AppError("Sign in required.", 401)
    return subject


_jwks_clients: dict[str, jwt.PyJWKClient] = {}


def verify_cognito_token(token: str, *, region: str, user_pool_id: str, app_client_id: str) -> dict:
    if not user_pool_id or not app_client_id or not region:
        raise ConfigurationError(
            "AUTH_MODE=cognito requires COGNITO_REGION, COGNITO_USER_POOL_ID, and COGNITO_APP_CLIENT_ID."
        )
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
    jwks_url = f"{issuer}/.well-known/jwks.json"
    try:
        client = _jwks_clients.get(jwks_url)
        if client is None:
            client = jwt.PyJWKClient(jwks_url)
            _jwks_clients[jwks_url] = client
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=app_client_id,
            issuer=issuer,
        )
    except ConfigurationError:
        raise
    except Exception as exc:
        raise AppError("Amazon Cognito rejected this token.", 401) from exc
    subject = payload.get("sub")
    email = payload.get("email")
    if not isinstance(subject, str) or not isinstance(email, str):
        raise AppError("The Cognito token is missing sub or email.", 401)
    name = payload.get("name") or payload.get("cognito:username") or email
    return {"id": subject, "email": email.lower(), "name": str(name)}
