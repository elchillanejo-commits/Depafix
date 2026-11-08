from fastapi import APIRouter, HTTPException
from app.models import LoginRequest

router = APIRouter()

@router.post("/login")
def login(data: LoginRequest):
    if data.email == "test@depafix.cl" and data.password == "1234":
        return {"access_token": "fake-jwt-token-para-pruebas", "token_type": "bearer", "empresa_id": "uuid-fake"}
    raise HTTPException(status_code=401, detail="Credenciales incorrectas")
