#!/usr/bin/env python3
import sys

ELEMENTOS = {
    "agua": {"herramienta": "scrapy", "comando": "scrapy startproject scraper_agua"},
    "aire": {"herramienta": "mautic (requiere Docker)", "comando": "docker run mautic/mautic"},
    "fuego": {"herramienta": "pdfplumber + celery", "comando": "celery -A tareas worker"},
    "otec": {"herramienta": "moodle (requiere Docker)", "comando": "docker run moodle/moodle"},
    "tierra": {"herramienta": "ifcopenshell", "comando": "python3 -c 'import ifcopenshell'"}
}

def ejecutar_elemento(elemento):
    if elemento not in ELEMENTOS:
        print(f"❌ Elemento '{elemento}' no reconocido.")
        print(f"   Disponibles: {', '.join(ELEMENTOS.keys())}")
        sys.exit(1)
    info = ELEMENTOS[elemento]
    print(f"🚀 Elemento: {elemento.upper()}")
    print(f"   Herramienta: {info['herramienta']}")
    print(f"   Comando: {info['comando']}")
    print(f"   ✅ Listo.")

def main():
    if len(sys.argv) < 2:
        print(f"Uso: python3 ejecutar_elemento.py <elemento>")
        print(f"Elementos: {', '.join(ELEMENTOS.keys())}")
        sys.exit(1)
    ejecutar_elemento(sys.argv[1].lower())

if __name__ == "__main__":
    main()
