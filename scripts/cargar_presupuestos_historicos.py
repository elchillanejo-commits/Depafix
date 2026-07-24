"""
Carga histórica de presupuestos reales desde ~/Escritorio/PPTOS/ a Supabase
(clientes, presupuestos, partidas_presupuesto, items_catalogo).

Reusa el parser de fichas "Costos Internos" (.tabla-cuenta) de
migrar_presupuestos_pdf.py y agrega un segundo parser para las fichas de
"Cotización" cara al cliente (.lista-items), formato usado por California
2520. Solo procesa .html -- los .pdf de la carpeta son impresiones de esos
mismos html y pueden quedar desactualizados si el html se corrigió después
(confirmado con el caso Vista Colón depto 710).

Idempotente: mismo criterio que migrar_presupuestos_pdf.py (upsert por
`codigo` en presupuestos, reinserta partidas, dedupe por `nombre_normalizado`
en items_catalogo). Además, antes de crear un ítem nuevo en el catálogo,
busca si ya existe un ítem cuyo nombre es un subconjunto de tokens del nuevo
(ej. "Extras" ⊂ "Extras (logística, bencina y supervisión)") y en ese caso
lo agrega como sinónimo en vez de crear una fila casi-duplicada -- evitamos
así reintroducir el bug de empate de _mejor_match_catalogo que ya se corrigió
en api.py.

Uso:
    python scripts/cargar_presupuestos_historicos.py [ruta_carpeta]
"""

import os
import sys

from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.db_manager import DatabaseManager  # noqa: E402
from scripts.migrar_presupuestos_pdf import (  # noqa: E402
    categorizar,
    normalizar_nombre,
    parsear_html as parsear_html_tabla,
    parsear_monto,
    registrar_error,
    upsert_cliente,
    upsert_presupuesto,
)

CARPETA_DEFAULT = os.path.expanduser("~/Escritorio/PPTOS")

# Documentos que no son fichas de presupuesto real y no deben migrarse:
# - dende.html: mini-juego sin relación con presupuestos.
# - Vista Colon PPTO.html (raíz): borrador sin depto identificado ("detalle
#   pendiente"), con precios (plafón $45.000) que quedaron superados por las
#   fichas por depto en Las condes/ (710/810/1111/602, todas ya corregidas a
#   $40.000). Migrarlo reintroduciría precios obsoletos en items_catalogo.
EXCLUIR = {"dende.html", "Vista Colon PPTO.html"}

PREFIJOS_DIRECCION = [
    ("vista colon", "VC"),
    ("briones luco", "BL"),
    ("california", "CAL"),
]


def parsear_html_lista(ruta_html: str):
    """Parsea fichas de Cotización cara al cliente (.lista-items .item/.precio)."""
    with open(ruta_html, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    datos = {}
    for fila in soup.select(".fila-dato"):
        label_el = fila.select_one(".label")
        valor_el = fila.select_one(".valor")
        if not label_el or not valor_el:
            continue
        import unicodedata

        label = label_el.get_text(strip=True).rstrip(":").lower()
        label = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii")
        datos[label] = valor_el.get_text(strip=True)

    items = []
    for li in soup.select(".lista-items li"):
        nombre_el = li.select_one(".item")
        precio_el = li.select_one(".precio")
        if not nombre_el or not precio_el:
            continue
        nombre = nombre_el.get_text(strip=True)
        precio = parsear_monto(precio_el.get_text(strip=True))
        items.append({"nombre": nombre, "cantidad": 1, "precio_unitario": precio, "monto": precio})

    total = 0.0
    for fila in soup.select(".resumen-precios .fila"):
        texto = fila.get_text(" ", strip=True).lower()
        if "subtotal" in texto:
            total = parsear_monto(fila.get_text(strip=True))
            break

    direccion = datos.get("direccion", "")
    import re

    m = re.search(r"(\d{3,4})\s*$", direccion)
    depto = m.group(1) if m else None

    return {
        "cliente_nombre": datos.get("cliente"),
        "telefono": datos.get("telefono"),
        "direccion": direccion,
        "comuna": datos.get("comuna"),
        "depto": depto,
        "items": items,
        "total": total,
    }


def detectar_formato(ruta_html: str) -> str | None:
    with open(ruta_html, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    if soup.select(".tabla-cuenta tbody tr"):
        return "tabla"
    if soup.select(".lista-items li"):
        return "lista"
    return None


def codigo_desde_direccion(direccion: str, depto: str) -> tuple[str, str]:
    import unicodedata

    d = unicodedata.normalize("NFKD", direccion or "").encode("ascii", "ignore").decode("ascii").lower()
    prefijo = next((p for clave, p in PREFIJOS_DIRECCION if clave in d), "PPTO")
    return prefijo, f"{prefijo}-{depto or 'SN'}"


def _tokens(texto: str) -> set[str]:
    """Tokeniza y aplica stemming por palabra (a diferencia de normalizar_nombre,
    que solo recorta el sufijo de la frase completa y falla en frases largas,
    ej. "Extras" -> "extra" pero "Extras (logística...)" conserva "extras")."""
    import re
    import unicodedata

    n = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    tokens = set()
    for palabra in n.split():
        if palabra.endswith("es") and len(palabra) > 4:
            palabra = palabra[:-2]
        elif palabra.endswith("s") and len(palabra) > 3:
            palabra = palabra[:-1]
        tokens.add(palabra)
    return tokens


def upsert_item_catalogo_seguro(client, nombre: str, precio_interno: float, origen: str) -> str:
    """Como upsert_item_catalogo, pero evita crear casi-duplicados.

    1) Match exacto por nombre_normalizado -> actualiza precio (mismo ítem, misma redacción).
    2) Si no hay match exacto, busca un ítem existente cuyo nombre sea un
       subconjunto de tokens del nombre nuevo (ej. "Extras" ⊂ "Extras
       (logística, bencina y supervisión)"). En ese caso NO se crea fila
       nueva ni se pisa el precio canónico (hay variación real de tarifa
       entre proyectos) -- se agrega el nombre completo como sinónimo, para
       que el matcher de /budget/generate lo reconozca igual.
    3) Si no hay ningún parecido, se crea un ítem nuevo.

    Devuelve una nota legible sobre qué acción se tomó, para el reporte.
    """
    nombre_normalizado = _norm_join(nombre)
    existente = (
        client.table("items_catalogo")
        .select("id,precio_interno")
        .eq("nombre_normalizado", nombre_normalizado)
        .limit(1)
        .execute()
        .data
    )
    if existente:
        precio_actual = existente[0].get("precio_interno") or 0
        # No pisar el precio canónico en un match exacto: el mismo nombre puede
        # tener tarifas distintas según el proyecto (confirmado con Vista Colón
        # depto 602, que sobrescribió Plafones LED $40.000 -> $9.990 al ser el
        # último archivo procesado). Solo se reporta la discrepancia.
        if abs(precio_actual - precio_interno) > 1:
            return (
                f"SIN CAMBIOS (revisar manualmente): {nombre} -- catálogo tiene ${precio_actual:,.0f}, "
                f"{origen} usa ${precio_interno:,.0f}"
            )
        return f"sin cambios (match exacto, mismo precio): {nombre}"

    catalogo = client.table("items_catalogo").select("id,nombre,sinonimos").execute().data or []

    nombre_lower = nombre.strip().lower()
    for it in catalogo:
        variantes = [it["nombre"], *(it.get("sinonimos") or [])]
        if nombre_lower in {v.strip().lower() for v in variantes}:
            return f"ya era sinónimo de {it['nombre']!r}, sin cambios"

    tokens_nuevo = _tokens(nombre)
    for it in catalogo:
        tokens_existente = _tokens(it["nombre"])
        if tokens_existente and tokens_existente.issubset(tokens_nuevo) and len(tokens_existente) >= 1:
            sinonimos = list(it.get("sinonimos") or [])
            if nombre not in sinonimos:
                sinonimos.append(nombre)
                client.table("items_catalogo").update({"sinonimos": sinonimos}).eq("id", it["id"]).execute()
                return f"fusionado como sinónimo de {it['nombre']!r} (precio canónico ${it.get('precio_interno', 0):,.0f} sin tocar, variante real ${precio_interno:,.0f} en {origen})"
            return f"ya era sinónimo de {it['nombre']!r}, sin cambios"

    client.table("items_catalogo").insert(
        {
            "nombre": nombre,
            "nombre_normalizado": nombre_normalizado,
            "categoria": categorizar(nombre),
            "precio_interno": precio_interno,
            "precio_cliente": None,
            "observaciones": f"Cargado desde histórico ({origen}).",
        }
    ).execute()
    return f"creado: {nombre} (${precio_interno:,.0f})"


def _norm_join(nombre: str) -> str:
    from scripts.migrar_presupuestos_pdf import normalizar_nombre as _n

    return _n(nombre)


def migrar_archivo(client, ruta_html: str):
    formato = detectar_formato(ruta_html)
    if formato is None:
        return None, "sin estructura de presupuesto reconocida (omitido)"

    datos = parsear_html_tabla(ruta_html) if formato == "tabla" else parsear_html_lista(ruta_html)
    if not datos["items"]:
        registrar_error(client, "cargar_presupuestos_historicos", "sin items detectados", {"archivo": ruta_html})
        return None, "sin items detectados"

    cliente_id = upsert_cliente(
        client, datos["cliente_nombre"] or "Cliente sin nombre", datos["telefono"], datos["direccion"], datos["comuna"]
    )

    prefijo, codigo = codigo_desde_direccion(datos["direccion"], datos["depto"])
    nombre_presupuesto = f"{datos['direccion'] or prefijo} - Depto {datos['depto']}" if datos["depto"] else (datos["direccion"] or prefijo)
    descripcion = f"Migrado desde {os.path.basename(ruta_html)}"

    presupuesto_id = upsert_presupuesto(client, codigo, nombre_presupuesto, descripcion, cliente_id, datos["total"])

    notas_catalogo = []
    for orden, item in enumerate(datos["items"]):
        nota = upsert_item_catalogo_seguro(client, item["nombre"], item["precio_unitario"], origen=os.path.basename(ruta_html))
        notas_catalogo.append(nota)
        client.table("partidas_presupuesto").insert(
            {
                "presupuesto_id": presupuesto_id,
                "descripcion": item["nombre"],
                "cantidad": item["cantidad"],
                "precio_unitario": item["precio_unitario"],
                "orden": orden,
            }
        ).execute()

    return {
        "codigo": codigo,
        "presupuesto_id": presupuesto_id,
        "items": len(datos["items"]),
        "total": datos["total"],
        "notas_catalogo": notas_catalogo,
    }, None


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else CARPETA_DEFAULT
    if not os.path.isdir(carpeta):
        print(f"No existe la carpeta: {carpeta}")
        sys.exit(1)

    client = DatabaseManager().get_service_client()

    htmls = []
    for root, _dirs, files in os.walk(carpeta):
        for f in files:
            if f.lower().endswith(".html") and f not in EXCLUIR:
                htmls.append(os.path.join(root, f))

    if not htmls:
        print(f"No se encontraron .html en {carpeta}")
        sys.exit(0)

    resultados = []
    for ruta in sorted(htmls):
        try:
            r, motivo_omision = migrar_archivo(client, ruta)
            if r:
                resultados.append((ruta, r))
                print(f"OK  {os.path.basename(ruta)} -> {r['codigo']} ({r['items']} items, total ${r['total']:,.0f})".replace(",", "."))
                for nota in r["notas_catalogo"]:
                    print(f"      catálogo: {nota}")
            else:
                print(f"OMITIDO {os.path.basename(ruta)}: {motivo_omision}")
        except Exception as e:
            registrar_error(client, "cargar_presupuestos_historicos", str(e), {"archivo": ruta})

    excluidos = [f for f in os.listdir(carpeta) if f in EXCLUIR]
    if excluidos:
        print(f"\nExcluidos explícitamente (no son fichas de presupuesto válidas): {excluidos}")

    print(f"\nMigrados {len(resultados)} de {len(htmls)} archivos procesables.")


if __name__ == "__main__":
    main()
