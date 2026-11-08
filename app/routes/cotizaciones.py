from fastapi import APIRouter, HTTPException
from app.models import CotizacionCreate, CotizacionResponse
import uuid
import os

# Importamos la lógica dura desde la capa de datos
from src.data.crear_presupuesto import procesar_presupuesto

router = APIRouter()

@router.post("", response_model=CotizacionResponse, status_code=201)
async def generar_cotizacion(payload: CotizacionCreate):
    try:
        cotizacion_id = uuid.uuid4()
        pdf_filename = f"COT-{cotizacion_id}.pdf"
        ruta_pdf_tmp = os.path.join("/tmp", pdf_filename)
        
        resultado_financiero = procesar_presupuesto(
            id_cotizacion=str(cotizacion_id),
            datos_proyecto=payload.model_dump(),
            ruta_salida=ruta_pdf_tmp
        )
        
        return CotizacionResponse(
            id_cotizacion=cotizacion_id,
            resumen_financiero={
                "subtotal_venta_neto": resultado_financiero.get("subtotal_venta_neto", 0.0),
                "monto_iva": resultado_financiero.get("monto_iva", 0.0),
                "total_presupuesto_bruto": resultado_financiero.get("total_presupuesto_bruto", 0.0)
            },
            pdf_url=ruta_pdf_tmp
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Fallo crítico en el motor de cotización: {str(e)}"
        )
