import argparse
import os
import sys
import webbrowser
from pathlib import Path

from app.core.serviu import PartidaNoEncontrada, PrecioNoConfiable, calcular

RAIZ = Path(__file__).resolve().parent
TEMPLATE = RAIZ / "presupuesto_template.html"


def generar_presupuesto_html(codigo_partida: str, comuna: str, magnitud: float, abrir: bool = False) -> Path:
    """Genera el presupuesto SERVIU validando precio y usando Decimal."""
    resultado = calcular(codigo_partida, magnitud, comuna)

    with TEMPLATE.open("r", encoding="utf-8") as archivo:
        template = archivo.read()

    html = (
        template.replace("{comuna}", resultado["comuna"])
        .replace("{partida}", resultado["nombre"])
        .replace(
            "{magnitud}",
            f"{resultado['magnitud']:g} {resultado['unidad']}",
        )
        .replace("{precio_unitario}", f"{resultado['precio_unitario']:,.0f}")
        .replace("{total_neto}", f"{resultado['total_neto']:,.2f}")
        .replace("{iva}", f"{resultado['iva']:,.2f}")
        .replace("{total_final}", f"{resultado['total_final']:,.2f}")
    )

    output_file = RAIZ / f"presupuesto_{codigo_partida.lower()}.html"
    output_file.write_text(html, encoding="utf-8")

    print(
        f"OK {output_file.name} | {resultado['nombre']} | "
        f"precio SERVIU ${resultado['precio_unitario']:,.0f} | "
        f"neto ${resultado['total_neto']:,.2f} | "
        f"IVA ${resultado['iva']:,.2f} | total ${resultado['total_final']:,.2f}"
    )
    if abrir:
        webbrowser.open(f"file://{output_file}")
    return output_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Cotizador local con precios oficiales SERVIU")
    parser.add_argument("codigo", nargs="?", default="CER-001", help="Código de partida (ej. CER-001)")
    parser.add_argument("comuna", nargs="?", default="Ñuñoa", help="Comuna de la obra")
    parser.add_argument("magnitud", nargs="?", type=float, default=50.0, help="Superficie o cantidad")
    parser.add_argument("--open", action="store_true", help="Abrir el HTML en el navegador")
    args = parser.parse_args()

    try:
        generar_presupuesto_html(args.codigo, args.comuna, args.magnitud, args.open)
    except (PartidaNoEncontrada, PrecioNoConfiable, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
