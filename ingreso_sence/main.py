#!/usr/bin/env python3
"""Orquestador ingreso SENCE: config → detección → DJ + Carta + Contratos → paquete."""
from pathlib import Path
from pypdf import PdfWriter, PdfReader

import comun
import dj
import carta
import contratos

BASE = Path(__file__).resolve().parent


def main():
    cfg = comun.cargar_config(interactivo=True)

    carpeta = Path(cfg.get("carpeta_curso") or comun.pedir("carpeta del curso", str(BASE / "curso")))
    archivos = comun.detectar_archivos(carpeta)
    print(f"Detectados: {', '.join(archivos) or 'ninguno'}")

    salida = comun.SALIDA / cfg["codigo_sence"]
    salida.mkdir(parents=True, exist_ok=True)         # Regla de Oro

    generados = []
    generados.append(("Declaración Jurada", dj.generar(cfg, archivos, salida)))
    generados.append(("Contratos", contratos.generar(cfg, archivos, salida)))
    # La carta lista lo realmente generado, y va primera en el paquete
    generados.insert(0, ("Carta Conductora",
                         carta.generar(cfg, [e for e, _ in generados], salida)))

    paquete = salida / f"Ingreso_SENCE_{cfg['codigo_sence']}.pdf"
    escritor = PdfWriter()
    for _, ruta in generados:
        for pagina in PdfReader(str(ruta)).pages:
            escritor.add_page(pagina)
    with open(paquete, "wb") as f:
        escritor.write(f)

    print("\nGenerado:")
    for etiqueta, ruta in generados:
        print(f"  • {etiqueta}: {ruta.name}")
    print(f"\nPaquete final → {paquete}")


if __name__ == "__main__":
    main()
