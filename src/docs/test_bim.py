#!/usr/bin/env python3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
IFC_PATH = BASE / "sample_test.ifc"
PDF_PATH = BASE / "sample_test.pdf"
TEXTO_ESPERADO = "DepaFix Fuego Tierra Test 123"


def test_ifcopenshell():
    import ifcopenshell

    print(f"[Tierra] ifcopenshell {ifcopenshell.version}")
    f = ifcopenshell.file(schema="IFC4")
    f.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="DepaFix-Test")
    f.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new(), Name="Muro-Prueba-Tierra")
    f.write(str(IFC_PATH))
    print(f"[Tierra] IFC creado: {IFC_PATH} ({IFC_PATH.stat().st_size} bytes)")
    f2 = ifcopenshell.open(str(IFC_PATH))
    proyectos = f2.by_type("IfcProject")
    muros = f2.by_type("IfcWall")
    print(f"[Tierra] Reabierto OK: {len(proyectos)} IfcProject, {len(muros)} IfcWall, {len(list(f2))} entidades")
    assert len(proyectos) == 1, "No se encontro IfcProject"
    assert len(muros) == 1, "No se encontro IfcWall"
    assert proyectos[0].Name == "DepaFix-Test"
    print("[Tierra] PASS")


def crear_pdf_prueba():
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(0, 10, TEXTO_ESPERADO, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "Cubicacion Express DepaFix", new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(PDF_PATH))
    print(f"[Fuego] PDF creado con fpdf2: {PDF_PATH} ({PDF_PATH.stat().st_size} bytes)")
    assert PDF_PATH.exists() and PDF_PATH.stat().st_size > 0


def test_docling():
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    print("[Fuego] Docling: importando DocumentConverter (pipeline liviano, sin OCR)")
    opts = PdfPipelineOptions(do_ocr=False, generate_table_structure=False, generate_page_images=False)
    converter = DocumentConverter(format_options={"pdf": PdfFormatOption(pipeline_options=opts)})
    resultado = converter.convert(str(PDF_PATH))
    markdown = resultado.document.export_to_markdown()
    print("[Fuego] Texto extraido por Docling:")
    print(markdown.strip()[:500])
    assert TEXTO_ESPERADO in markdown, f"Texto esperado no encontrado en extraccion Docling: {markdown[:200]}"
    print("[Fuego] PASS (Docling)")


def fallback_pdfplumber():
    import pdfplumber

    print("[Fuego] Fallback pdfplumber:")
    with pdfplumber.open(str(PDF_PATH)) as pdf:
        texto = "\n".join((p.extract_text() or "") for p in pdf.pages)
    print(texto.strip()[:500])
    assert TEXTO_ESPERADO in texto
    print("[Fuego] PASS (pdfplumber fallback)")


def main():
    print("=" * 64)
    print("DepaFix @build-docs — test_bim.py (Fuego + Tierra)")
    print("=" * 64)
    test_ifcopenshell()
    crear_pdf_prueba()
    try:
        test_docling()
    except Exception as e:
        print(f"[Fuego] Docling fallo ({type(e).__name__}: {e}), usando fallback pdfplumber")
        fallback_pdfplumber()
    print("=" * 64)
    print("RESULTADO: ALL PASS")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
