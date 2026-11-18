import io
import logging
import os
import traceback
from typing import List

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.auth_supabase import get_current_user
from app.core.database import get_db
from app.core.security import enforce_rate_limit, verify_api_key
from app.presupuesto_csv import router as presupuesto_csv_router
from app.routers import cotizaciones as cotizaciones_router
from app.routers import rag as rag_router
from weasyprint import HTML

logger = logging.getLogger(__name__)

app = FastAPI(
    title="DepaFix SaaS API",
    description="API para el Motor de Cotizaciones y Gestión de Usuarios",
    version="1.0.0",
)

# CORS configurable (fallback seguro para el dashboard Streamlit local)
def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:8501,http://localhost:8502")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers públicos protegidos con X-API-Key (si está configurada) + rate limit
_public_dependencies = [Depends(verify_api_key), Depends(enforce_rate_limit)]

app.include_router(cotizaciones_router.router, dependencies=_public_dependencies)
app.include_router(presupuesto_csv_router, dependencies=_public_dependencies)
app.include_router(rag_router.router, dependencies=_public_dependencies)


# ==========================================
# HEALTHCHECK
# ==========================================
@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "depafix-api"}


@app.get("/ready", tags=["Health"])
async def ready():
    """Deep check: comprueba que Supabase responde y los permisos son válidos."""
    try:
        db = await get_db()
        await db.table("cotizaciones").select("id").limit(1).execute()
    except Exception as exc:
        logger.warning("Ready check fallido: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Base de datos no disponible ({type(exc).__name__}).",
        ) from exc
    return {"status": "ready", "database": "connected"}


# ==========================================
# AUTH: /api/v1/me (protegido con Supabase JWT)
# ==========================================
@app.get("/api/v1/me", tags=["Auth"])
async def read_me(user: dict = Depends(get_current_user)):
    return {
        "user_id": user.get("sub"),
        "email": user.get("email"),
        "role": user.get("role"),
    }


# ==========================================
# PDF desde JSON (WeasyPrint)
# ==========================================
class PresupuestoItem(BaseModel):
    desc: str
    precio: float


class PresupuestoRequest(BaseModel):
    direccion: str
    items: List[PresupuestoItem]
    total_neto: float


@app.post("/api/v1/presupuesto/pdf", tags=["Presupuestos"])
async def presupuesto_pdf(
    req: PresupuestoRequest,
    user: dict = Depends(get_current_user),
):
    try:
        filas_html = "".join(
            f"<tr><td>{item.desc}</td><td style='text-align:right'>${item.precio:,.0f}</td></tr>".replace(",", ".")
            for item in req.items
        )
        iva = req.total_neto * 0.19
        total_pagar = req.total_neto + iva

        html = f"""
        <html>
        <head><meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; color: #1e2f44; }}
            .header {{ background: #0b2a44; color: white; padding: 15px; border-bottom: 4px solid #f39c12; }}
            .direccion {{ background: #e8f0f9; padding: 8px 12px; border-left: 4px solid #f39c12; margin: 15px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th {{ background: #1a4b75; color: white; padding: 8px; }}
            td {{ padding: 6px 8px; border-bottom: 1px solid #e5ebf6; }}
            .totales {{ margin-top: 20px; border: 2px solid #f39c12; border-radius: 8px; padding: 10px 15px; }}
            .fila {{ display: flex; justify-content: space-between; padding: 4px 0; }}
            .destacado {{ font-size: 18px; font-weight: bold; color: #d4850a; }}
        </style></head>
        <body>
            <div class="header"><h1>DEPAFIX</h1></div>
            <div class="direccion"><strong>Dirección:</strong> {req.direccion}</div>
            <table>
                <thead><tr><th>Descripción</th><th style="text-align:right">Precio</th></tr></thead>
                <tbody>{filas_html}</tbody>
            </table>
            <div class="totales">
                <div class="fila"><span>Total Neto</span><span>${req.total_neto:,.0f}</span></div>
                <div class="fila"><span>IVA (19%)</span><span>${iva:,.0f}</span></div>
                <div class="fila destacado"><span>Total a Pagar</span><span>${total_pagar:,.0f}</span></div>
            </div>
        </body></html>
        """
        pdf_bytes = HTML(string=html).write_pdf()
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="presupuesto.pdf"'},
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


class SkillItem(BaseModel):
    descripcion: str
    precio_unitario: float


class SkillPresupuestoRequest(BaseModel):
    direccion: str
    items: List[SkillItem]
    total_neto: float


@app.post("/api/v1/presupuesto/desde-skill", tags=["Presupuestos"])
async def presupuesto_desde_skill(
    req: SkillPresupuestoRequest,
    user: dict = Depends(get_current_user),
):
    normalizado = PresupuestoRequest(
        direccion=req.direccion,
        items=[
            PresupuestoItem(desc=item.descripcion, precio=item.precio_unitario)
            for item in req.items
        ],
        total_neto=req.total_neto,
    )
    return await presupuesto_pdf(normalizado, user)
