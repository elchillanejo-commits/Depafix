from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os

def justificar_docx(ruta_archivo):
    doc = Document(ruta_archivo)
    for para in doc.paragraphs:
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    nuevo_nombre = ruta_archivo.replace(".docx", "_justificado.docx")
    doc.save(nuevo_nombre)
    print(f"✅ Documento justificado guardado como: {nuevo_nombre}")

justificar_docx('CONTRATO DE CAPACITACIÓN.docx')
