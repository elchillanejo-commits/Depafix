import os
import uuid
import json
import hashlib
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, dsa, ec
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ingesta Inmutable")

# Configuración de la base de datos
DATABASE_URL = os.getenv("SUPABASE_DB_URL")
if not DATABASE_URL:
    raise ValueError("SUPABASE_DB_URL no configurada")

engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Modelo de la solicitud
class IngestRequest(BaseModel):
    idempotency_key: str
    user_id: str
    data: dict
    signature: str   # firma en base64 de la data (o de todo el payload)

class IngestResponse(BaseModel):
    record_id: str
    created: bool
    message: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/ingest", response_model=IngestResponse)
async def ingest(payload: IngestRequest):
    """
    Endpoint idempotente:
    1. Verifica la firma con la clave pública del usuario.
    2. Busca idempotency_key en records.
    3. Si existe, devuelve el record_id existente.
    4. Si no, inserta el nuevo registro y devuelve el nuevo record_id.
    """
    # 1. Obtener la clave pública del usuario desde la tabla user_keys
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT public_key, algorithm FROM user_keys WHERE user_id = :uid"),
            {"uid": payload.user_id}
        ).first()
    if not result:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    public_key_pem = result.public_key
    algorithm = result.algorithm

    # 2. Verificar la firma
    try:
        # Convertir PEM a clave pública
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        
        # Decodificar la firma de base64
        signature_bytes = bytes.fromhex(payload.signature)  # Asumimos hex; ajustar si es base64

        # Determinar el mensaje que se firmó (usamos el data serializado + idempotency_key)
        # Puede ajustarse según el acuerdo de firma.
        message = json.dumps(payload.data, sort_keys=True).encode()
        
        if algorithm.upper() == 'RSA':
            public_key.verify(
                signature_bytes,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        elif algorithm.upper() == 'ECDSA':
            public_key.verify(
                signature_bytes,
                message,
                ec.ECDSA(hashes.SHA256())
            )
        else:
            raise HTTPException(status_code=400, detail="Algoritmo no soportado")
    except Exception as e:
        logger.error(f"Firma inválida: {e}")
        raise HTTPException(status_code=401, detail="Firma inválida")

    # 3. Verificar idempotencia
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id FROM records WHERE idempotency_key = :key"),
            {"key": payload.idempotency_key}
        ).first()
        if result:
            # Ya existe, devolver el record_id existente
            return IngestResponse(
                record_id=str(result.id),
                created=False,
                message="Registro ya existente (idempotencia)"
            )

    # 4. Insertar nuevo registro
    new_record_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO records (id, idempotency_key, user_id, data)
                VALUES (:id, :key, :uid, :data)
            """),
            {
                "id": new_record_id,
                "key": payload.idempotency_key,
                "uid": payload.user_id,
                "data": json.dumps(payload.data)
            }
        )

    logger.info(f"Registro creado: {new_record_id} con key {payload.idempotency_key}")
    return IngestResponse(
        record_id=str(new_record_id),
        created=True,
        message="Registro creado exitosamente"
    )
