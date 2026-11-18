import io
import csv
import traceback
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fpdf import FPDF

router = APIRouter(prefix="/api/v1/presupuesto", tags=["presupuestos"])


class PresupuestoPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(11, 42, 68)
        self.cell(0, 10, "DEPAFIX", ln=True, align="L")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(243, 156, 18)
        self.cell(0, 6, "Mantención · Aseo · Cerrajería", ln=True, align="L")
        self.set_draw_color(243, 156, 18)
        self.set_line_width(0.8)
        self.line(10, 28, 200, 28)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cell(0, 10, f"Generado por DepaFix · {fecha} · Página {self.page_no()}", align="C")


def parse_csv_en_memoria(contenido: bytes) -> list[dict]:
    try:
        texto = contenido.decode("utf-8-sig")  # utf-8-sig remueve BOM
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1")

    print(f"[DEBUG] CSV recibido, {len(texto)} chars, primeras 100: {texto[:100]!r}")

    reader = csv.DictReader(io.StringIO(texto))
    print(f"[DEBUG] Columnas detectadas: {reader.fieldnames}")

    filas = []
    for i, row in enumerate(reader, start=1):
        if not any((v or "").strip() for v in row.values()):
            continue
        desc = (row.get("descripcion") or row.get("descripción") or row.get("item") or "").strip()
        precio_raw = (row.get("precio") or row.get("monto") or "0").strip().replace(".", "").replace(",", ".")
        if not desc:
            raise HTTPException(status_code=400, detail=f"Fila {i}: falta la columna 'descripcion' o está vacía.")
        try:
            precio = float(precio_raw)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Fila {i}: precio inválido ('{precio_raw}').")
        filas.append({"descripcion": desc, "precio": precio})

    if not filas:
        raise HTTPException(status_code=400, detail="El CSV no contiene filas válidas.")
    return filas


@router.post("/csv")
async def presupuesto_desde_csv(file: UploadFile = File(...)):
    try:
        print(f"[DEBUG] Archivo recibido: {file.filename}, content_type: {file.content_type}")

        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="El archivo debe ser .csv")

        contenido = await file.read()
        print(f"[DEBUG] Bytes leídos: {len(contenido)}")

        filas = parse_csv_en_memoria(contenido)
        print(f"[DEBUG] Filas válidas: {len(filas)}")

        total = sum(f["precio"] for f in filas)

        pdf = PresupuestoPDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(30, 47, 68)
        pdf.cell(0, 8, f"Presupuesto generado desde CSV: {file.filename}", ln=True)
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(26, 75, 117)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(140, 8, "Descripción", border=1, fill=True)
        pdf.cell(40, 8, "Precio", border=1, fill=True, align="R")
        pdf.ln()

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(30, 47, 68)
        fill = False
        for f in filas:
            pdf.set_fill_color(248, 250, 255) if fill else pdf.set_fill_color(255, 255, 255)
            pdf.cell(140, 7, f["descripcion"][:70], border=1, fill=True)
            pdf.cell(40, 7, f"${f['precio']:,.0f}".replace(",", "."), border=1, fill=True, align="R")
            pdf.ln()
            fill = not fill

        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(11, 42, 68)
        pdf.cell(140, 10, "Total Neto", border=1, align="L")
        pdf.set_text_color(212, 133, 10)
        pdf.cell(40, 10, f"${total:,.0f}".replace(",", "."), border=1, align="R")
        pdf.ln()

        iva = total * 0.19
        pdf.set_text_color(30, 47, 68)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(140, 7, "IVA (19%)", border=1)
        pdf.cell(40, 7, f"${iva:,.0f}".replace(",", "."), border=1, align="R")
        pdf.ln()
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(140, 9, "Total a Pagar", border=1)
        pdf.set_text_color(212, 133, 10)
        pdf.cell(40, 9, f"${(total + iva):,.0f}".replace(",", "."), border=1, align="R")
        pdf.ln()

        pdf_bytes = pdf.output(dest="S")
        if isinstance(pdf_bytes, str):
            pdf_bytes = pdf_bytes.encode("latin-1")

        filename = f"presupuesto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        print("[ERROR] Falló presupuesto_desde_csv:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")
