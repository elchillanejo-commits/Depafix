import os
from pathlib import Path

import jwt as pyjwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt as jose_jwt

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_LEGACY_JWT_SECRET = os.getenv("SUPABASE_LEGACY_JWT_SECRET")

if not SUPABASE_LEGACY_JWT_SECRET and SUPABASE_JWT_SECRET:
    if not SUPABASE_JWT_SECRET.startswith(("sb_", "eyJ")):
        SUPABASE_LEGACY_JWT_SECRET = SUPABASE_JWT_SECRET

SUPABASE_JWKS_URL = os.getenv("SUPABASE_JWKS_URL") or (
    f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else None
)

if not SUPABASE_URL and not SUPABASE_LEGACY_JWT_SECRET:
    raise RuntimeError(
        "Falta SUPABASE_URL (o SUPABASE_LEGACY_JWT_SECRET) en las variables de entorno."
    )

ASYMMETRIC_ALGORITHMS = ["ES256", "ES384", "ES512", "RS256", "RS384", "RS512", "EdDSA"]

security = HTTPBearer()

jwks_client = pyjwt.PyJWKClient(SUPABASE_JWKS_URL) if SUPABASE_JWKS_URL else None


def unauthorized(detail: str = "Token inválido o expirado") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_legacy_token(token: str) -> dict:
    if not SUPABASE_LEGACY_JWT_SECRET:
        raise unauthorized()

    return jose_jwt.decode(
        token,
        SUPABASE_LEGACY_JWT_SECRET,
        algorithms=["HS256"],
        audience="authenticated",
    )


def decode_jwks_token(token: str) -> dict:
    if jwks_client is None:
        raise unauthorized()

    signing_key = jwks_client.get_signing_key_from_jwt(token)

    return pyjwt.decode(
        token,
        signing_key.key,
        algorithms=ASYMMETRIC_ALGORITHMS,
        audience="authenticated",
        options={"require": ["exp", "sub"]},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials

    try:
        header = pyjwt.get_unverified_header(token)
        algorithm = header.get("alg", "")

        if algorithm == "HS256":
            payload = decode_legacy_token(token)
        else:
            payload = decode_jwks_token(token)
    except (JWTError, pyjwt.PyJWTError, ValueError, KeyError) as exc:
        raise unauthorized() from exc

    if not payload.get("sub"):
        raise unauthorized("Token sin usuario válido")

    return payload
