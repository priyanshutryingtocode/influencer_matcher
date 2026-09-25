from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from uuid import UUID

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from src import config


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None = None


_jwks_lock = Lock()
_jwks_client: PyJWKClient | None = None


def current_user(request: Request) -> AuthUser | None:
    if not config.AUTH_REQUIRED:
        return None
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise _unauthorized()
    token = header.removeprefix("Bearer ").strip()
    if not token:
        raise _unauthorized()
    try:
        payload = _decode_token(token)
    except Exception as exc:
        raise _unauthorized() from exc
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise _unauthorized()
    try:
        UUID(subject)
    except ValueError as exc:
        raise _unauthorized() from exc
    if payload.get("role") != "authenticated":
        raise _unauthorized()
    email = payload.get("email")
    return AuthUser(id=subject, email=email if isinstance(email, str) else None)


def current_user_id(request: Request) -> str | None:
    user = current_user(request)
    return user.id if user else None


def _decode_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    algorithm = header.get("alg")
    options = {"require": ["exp", "sub"], "verify_iss": bool(config.SUPABASE_ISSUER)}
    decode_args = {
        "audience": config.SUPABASE_JWT_AUDIENCE,
        "options": options,
    }
    if config.SUPABASE_ISSUER:
        decode_args["issuer"] = config.SUPABASE_ISSUER
    if algorithm == "HS256":
        if not config.SUPABASE_JWT_SECRET:
            raise RuntimeError("HS256 Supabase verification is not configured")
        return jwt.decode(token, config.SUPABASE_JWT_SECRET, algorithms=["HS256"], **decode_args)
    if algorithm in {"RS256", "ES256"}:
        if not config.SUPABASE_JWKS_URL:
            raise RuntimeError("Asymmetric Supabase verification is not configured")
        key = _get_jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["RS256", "ES256"], **decode_args)
    raise RuntimeError("Unsupported Supabase JWT algorithm")


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        with _jwks_lock:
            if _jwks_client is None:
                _jwks_client = PyJWKClient(config.SUPABASE_JWKS_URL)
    return _jwks_client


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "AUTH_REQUIRED", "message": "Sign in to use this resource."},
        headers={"WWW-Authenticate": "Bearer"},
    )
