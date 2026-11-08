import os
import uuid
from fastapi import APIRouter, HTTPException
from supabase import create_client, Client
from app.models import CotizacionCreate, CotizacionResponse
from src.data.crear_presupuesto import procesar_presupuesto

router = APIRouter()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Faltan credenciales de Supabase en las variables de entorno.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "cotizaciones_pdfs"

@router.post("", response_model=CotizacionResponse, status_code=201)
async def generar_cotizacion(payload: CotizacionCreate):
    try:
        cotizacion_id = uuid.uuid4()
        pdf_filename = f"COT-{cotizacion_id}.pdf"
        ruta_pdf_tmp = os.path.join("/tmp", pdf_filename)
        
        datos_proyecto = payload.model_dump()
        resultado_financiero = procesar_presupuesto(
            id_cotizacion=str(cotizacion_id),
            datos_proyecto=datos_proyecto,
            ruta_salida=ruta_pdf_tmp
        )
        
        with open(ruta_pdf_tmp, "rb") as f:
            supabase.storage.from_(BUCKET_NAME).upload(
                file=f,
                path=pdf_filename,
                file_options={"content-type": "application/pdf"}
            )
            
        url_publica = supabase.storage.from_(BUCKET_NAME).get_public_url(pdf_filename)
        
        if os.path.exists(ruta_pdf_tmp):
            os.remove(ruta_pdf_tmp)
            
        return CotizacionResponse(
            id_cotizacion=cotizacion_id,
            resumen_financiero={
                "subtotal_venta_neto": resultado_financiero.get("subtotal_venta_neto", 0.0),
                "monto_iva": resultado_financiero.get("monto_iva", 0.0),
                "total_presupuesto_bruto": resultado_financiero.get("total_presupuesto_bruto", 0.0)
            },
            pdf_url=url_publica
        )
    except Exception as e:
        if 'ruta_pdf_tmp' in locals() and os.path.exists(ruta_pdf_tmp):
            os.remove(ruta_pdf_tmp)
        raise HTTPException(status_code=500, detail=f"Fallo en el motor: {str(e)}")
