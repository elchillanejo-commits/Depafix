import os
import secrets

from fastapi import APIRouter, HTTPException
from app.models import LoginRequest

router = APIRouter()

TEST_EMAIL = os.getenv("DEPAFIX_TEST_EMAIL")
TEST_PASSWORD = os.getenv("DEPAFIX_TEST_PASSWORD")
TEST_TOKEN = os.getenv("DEPAFIX_TEST_TOKEN")


@router.post("/login")
def login(data: LoginRequest):
    if not (TEST_EMAIL and TEST_PASSWORD and TEST_TOKEN):
        raise HTTPException(
            status_code=503,
            detail="Login de prueba no configurado (faltan variables DEPAFIX_TEST_*).",
        )
    if secrets.compare_digest(data.email, TEST_EMAIL) and secrets.compare_digest(
        data.password, TEST_PASSWORD
    ):
        return {
            "access_token": TEST_TOKEN,
            "token_type": "bearer",
            "empresa_id": "uuid-fake",
        }
    raise HTTPException(status_code=401, detail="Credenciales incorrectas")
