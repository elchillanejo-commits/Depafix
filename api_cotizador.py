import os
import re
import sys
import subprocess
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from werkzeug.utils import secure_filename
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
SCRIPT = BASE_DIR / "procesar_subcontrato.py"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="DepaFix Cotizador API")


class TrabajadorFranquicia(BaseModel):
    remuneracion: float = Field(default=0, ge=0)


class CalcularFranquiciaRequest(BaseModel):
    rut_empresa: str = Field(..., min_length=1)
    trabajadores: list[TrabajadorFranquicia] = Field(default_factory=list)


def validar_proyecto(proyecto: str) -> bool:
    """Valida codigo de proyecto: solo alfanumerico, guion y guion bajo (evita path traversal)."""
    if not proyecto or not isinstance(proyecto, str):
        return False
    return all(c.isalnum() or c in ("-", "_") for c in proyecto)


def _parse_moneda(texto):
    if not texto:
        return 0
    s = re.sub(r"[^\d]", "", texto)
    return int(s) if s else 0


def _extraer_totales(ruta_html):
    """Lee el HTML generado y extrae neto, iva y total."""
    with open(ruta_html, "r", encoding="utf-8") as f:
        contenido = f.read()

    neto = 0
    iva = 0
    total = 0

    m_neto = re.search(r"Neto:\s*\$?([\d.,]+)", contenido)
    if m_neto:
        neto = _parse_moneda(m_neto.group(1))

    m_iva = re.search(r"IVA\s*\(19%\):\s*\$?([\d.,]+)", contenido)
    if m_iva:
        iva = _parse_moneda(m_iva.group(1))

    m_total = re.search(r"TOTAL:\s*\$?([\d.,]+)", contenido)
    if m_total:
        total = _parse_moneda(m_total.group(1))

    return neto, iva, total


@app.get("/api/materiales/{proyecto}")
def get_materiales(proyecto: str):
    if not validar_proyecto(proyecto):
        raise HTTPException(status_code=400, detail="Codigo de proyecto invalido")
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        cliente = create_client(supabase_url, supabase_key)
        res = (
            cliente.table("proyecto_materiales")
            .select("*")
            .eq("proyecto_codigo", proyecto)
            .execute()
        )
        return JSONResponse(
            status_code=200,
            content={"success": True, "data": res.data},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al consultar materiales: {e}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/calcular-franquicia")
def calcular_franquicia(payload: CalcularFranquiciaRequest):
    rut_empresa = payload.rut_empresa.strip()
    if not rut_empresa:
        raise HTTPException(status_code=400, detail="RUT de empresa invalido")

    from sence_tools import calcular_saldo_franquicia

    try:
        resultado = calcular_saldo_franquicia(
            rut_empresa,
            [trabajador.model_dump() for trabajador in payload.trabajadores],
        )
        return JSONResponse(
            status_code=200,
            content={"success": True, "data": resultado},
        )
    except HTTPException:
        raise
    except SystemExit as error:
        raise HTTPException(status_code=500, detail=str(error))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculando franquicia SENCE: {error}",
        )


@app.post("/cotizar")
async def cotizar(
    pdf: UploadFile = File(...),
    proyecto: str = Form(...),
    proveedor: str = Form(...),
    sku_prefix: str = Form(...),
    fecha_requerida: str = Form(...),
):
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")

    if not validar_proyecto(proyecto):
        raise HTTPException(status_code=400, detail="Codigo de proyecto invalido")

    ruta_pdf = None
    try:
        try:
            datetime.strptime(fecha_requerida, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Fecha requerida invalida (formato YYYY-MM-DD)")

        nombre_seguro = f"{uuid.uuid4().hex}_{secure_filename(pdf.filename)}"
        ruta_pdf = UPLOAD_DIR / nombre_seguro

        with open(ruta_pdf, "wb") as f:
            shutil.copyfileobj(pdf.file, f)

        cmd = [
            sys.executable,
            str(SCRIPT),
            "--archivo", str(ruta_pdf),
            "--proyecto", proyecto,
            "--proveedor", proveedor,
            "--sku-prefix", sku_prefix,
            "--fecha-requerida", fecha_requerida,
        ]

        resultado = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR),
        )

        if resultado.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Error ejecutando procesar_subcontrato.py: {resultado.stderr}",
            )

        ruta_html = OUTPUT_DIR / f"presupuesto_{proyecto}.html"
        if not ruta_html.exists():
            raise HTTPException(
                status_code=500,
                detail="No se genero el archivo de presupuesto HTML",
            )

        neto, iva, total = _extraer_totales(ruta_html)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "total_cliente": total,
                "total_iva": iva,
                "ruta_html": str(ruta_html),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if ruta_pdf is not None and ruta_pdf.exists():
            try:
                ruta_pdf.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


