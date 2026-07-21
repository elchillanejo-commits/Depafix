"""
Migra presupuestos reales (fichas de "Costos Internos" en HTML/PDF) a Supabase.

Los PDFs de la carpeta son impresiones de un .html gemelo con la misma
estructura (.fila-dato para los datos del cliente, .tabla-cuenta para los
ítems). Se parsea el HTML -- extraer texto de los PDF produce artefactos de
fuente (letras duplicadas) poco confiables.

Idempotente: usa `codigo` (único en presupuestos) para upsert, borra y
reinserta las partidas de cada presupuesto migrado, y usa
`nombre_normalizado` (único en items_catalogo) para deduplicar ítems.

Uso:
    python scripts/migrar_presupuestos_pdf.py [ruta_carpeta]
"""

import os
import re
import sys
import unicodedata

from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.db_manager import DatabaseManager  # noqa: E402

CARPETA_DEFAULT = os.path.expanduser("~/Escritorio/PPTOS/Las condes")

RE_ITEM_CON_CANTIDAD = re.compile(r"^(\d+)\s+(.+?)\s*\(\d+\s*[×xX]\s*\$?([\d.]+)\)$")
RE_MONTO = re.compile(r"[\d.]+")


def normalizar_nombre(nombre: str) -> str:
    """Normaliza un nombre de ítem para deduplicar (mayúsculas, plural simple, acentos)."""
    n = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    n = n.lower().strip()
    n = re.sub(r"\s+", " ", n)
    n = re.sub(r"[^a-z0-9 ]", "", n)
    if n.endswith("es") and len(n) > 4:
        n = n[:-2]
    elif n.endswith("s") and len(n) > 3:
        n = n[:-1]
    return n


def categorizar(nombre: str) -> str:
    n = nombre.lower()
    if "plafon" in n or "luz" in n or "luces" in n or "led" in n:
        return "iluminacion"
    if "soporte" in n or "tv" in n:
        return "montaje"
    if "llave" in n or "lavadora" in n:
        return "instalacion"
    if "mano de obra" in n:
        return "mano_de_obra"
    return "otros"


def parsear_monto(texto: str) -> float:
    m = RE_MONTO.search(texto.replace(".", ""))
    return float(m.group(0)) if m else 0.0


def parsear_html(ruta_html: str):
    with open(ruta_html, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    datos = {}
    for fila in soup.select(".fila-dato"):
        label_el = fila.select_one(".label")
        valor_el = fila.select_one(".valor")
        if not label_el or not valor_el:
            continue
        label = label_el.get_text(strip=True).rstrip(":").lower()
        label = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii")
        valor = valor_el.get_text(strip=True)
        datos[label] = valor

    filas = soup.select(".tabla-cuenta tbody tr")
    items = []
    total = 0.0
    for fila in filas:
        tds = fila.find_all("td")
        if len(tds) != 2:
            continue
        concepto = tds[0].get_text(strip=True)
        monto_texto = tds[1].get_text(strip=True)
        concepto_lower = concepto.lower()
        if "total" in concepto_lower:
            total = parsear_monto(monto_texto)
            continue
        if "iva" in concepto_lower or concepto_lower.strip() == "subtotal":
            continue

        monto = parsear_monto(monto_texto)
        match = RE_ITEM_CON_CANTIDAD.match(concepto)
        if match:
            cantidad = int(match.group(1))
            nombre = match.group(2).strip()
            precio_unitario = parsear_monto(match.group(3))
        else:
            cantidad = 1
            nombre = concepto
            precio_unitario = monto

        items.append(
            {
                "nombre": nombre,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "monto": monto,
            }
        )

    depto = datos.get("depto")
    direccion = datos.get("direccion", "")
    if not depto:
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


def registrar_error(client, contexto: str, mensaje: str, detalle: dict | None = None):
    try:
        client.table("error_logs").insert(
            {
                "modulo": "migrar_presupuestos_pdf",
                "funcion": contexto,
                "mensaje": mensaje,
                "metadata": detalle or {},
            }
        ).execute()
    except Exception as e:
        print(f"[WARN] no se pudo escribir en error_logs: {e}")
    print(f"[ERROR] {contexto}: {mensaje}")


def upsert_cliente(client, nombre: str, telefono: str | None, direccion: str | None, comuna: str | None) -> str:
    query = client.table("clientes").select("id").eq("nombre", nombre)
    if telefono:
        query = query.eq("telefono", telefono)
    existente = query.limit(1).execute().data
    if existente:
        cliente_id = existente[0]["id"]
        client.table("clientes").update(
            {"telefono": telefono, "direccion": direccion, "comuna": comuna}
        ).eq("id", cliente_id).execute()
        return cliente_id

    creado = (
        client.table("clientes")
        .insert({"nombre": nombre, "telefono": telefono, "direccion": direccion, "comuna": comuna})
        .execute()
    )
    return creado.data[0]["id"]


def upsert_item_catalogo(client, nombre: str, precio_interno: float):
    nombre_normalizado = normalizar_nombre(nombre)
    existente = (
        client.table("items_catalogo")
        .select("id")
        .eq("nombre_normalizado", nombre_normalizado)
        .limit(1)
        .execute()
        .data
    )
    if existente:
        client.table("items_catalogo").update(
            {"precio_interno": precio_interno, "updated_at": "now()"}
        ).eq("id", existente[0]["id"]).execute()
        return

    client.table("items_catalogo").insert(
        {
            "nombre": nombre,
            "nombre_normalizado": nombre_normalizado,
            "categoria": categorizar(nombre),
            "precio_interno": precio_interno,
            "precio_cliente": None,  # no hay tarifa cliente distinta en los documentos migrados
        }
    ).execute()


def upsert_presupuesto(client, codigo: str, nombre: str, descripcion: str, cliente_id: str, monto_total: float) -> int:
    existente = client.table("presupuestos").select("id").eq("codigo", codigo).limit(1).execute().data
    if existente:
        presupuesto_id = existente[0]["id"]
        client.table("presupuestos").update(
            {
                "nombre": nombre,
                "descripcion": descripcion,
                "cliente_id": cliente_id,
                "monto_total": monto_total,
                "estado": "migrado",
                "updated_at": "now()",
            }
        ).eq("id", presupuesto_id).execute()
    else:
        creado = (
            client.table("presupuestos")
            .insert(
                {
                    "codigo": codigo,
                    "nombre": nombre,
                    "descripcion": descripcion,
                    "cliente_id": cliente_id,
                    "monto_total": monto_total,
                    "estado": "migrado",
                }
            )
            .execute()
        )
        presupuesto_id = creado.data[0]["id"]

    # idempotente: se borran las partidas anteriores de este presupuesto y se reinsertan
    client.table("partidas_presupuesto").delete().eq("presupuesto_id", presupuesto_id).execute()
    return presupuesto_id


def migrar_archivo(client, ruta_html: str):
    datos = parsear_html(ruta_html)
    if not datos["items"]:
        registrar_error(client, "migrar_presupuestos_pdf", "sin items detectados", {"archivo": ruta_html})
        return None

    cliente_id = upsert_cliente(
        client, datos["cliente_nombre"] or "Cliente sin nombre", datos["telefono"], datos["direccion"], datos["comuna"]
    )

    depto = datos["depto"] or "SN"
    codigo = f"VC-{depto}"
    nombre = f"Vista Colón - Depto {depto}"
    descripcion = f"Migrado desde {os.path.basename(ruta_html)}"

    presupuesto_id = upsert_presupuesto(client, codigo, nombre, descripcion, cliente_id, datos["total"])

    for orden, item in enumerate(datos["items"]):
        upsert_item_catalogo(client, item["nombre"], item["precio_unitario"])
        client.table("partidas_presupuesto").insert(
            {
                "presupuesto_id": presupuesto_id,
                "descripcion": item["nombre"],
                "cantidad": item["cantidad"],
                "precio_unitario": item["precio_unitario"],
                "orden": orden,
            }
        ).execute()

    return {"codigo": codigo, "presupuesto_id": presupuesto_id, "items": len(datos["items"]), "total": datos["total"]}


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else CARPETA_DEFAULT
    if not os.path.isdir(carpeta):
        print(f"No existe la carpeta: {carpeta}")
        sys.exit(1)

    client = DatabaseManager().get_service_client()

    htmls = []
    for root, _dirs, files in os.walk(carpeta):
        for f in files:
            if f.lower().endswith(".html"):
                htmls.append(os.path.join(root, f))

    if not htmls:
        print(f"No se encontraron .html en {carpeta}")
        sys.exit(0)

    resultados = []
    for ruta in sorted(htmls):
        try:
            r = migrar_archivo(client, ruta)
            if r:
                resultados.append((ruta, r))
                print(f"OK  {os.path.basename(ruta)} -> {r['codigo']} ({r['items']} items, total ${r['total']:,.0f})".replace(",", "."))
        except Exception as e:
            registrar_error(client, "migrar_presupuestos_pdf", str(e), {"archivo": ruta})

    print(f"\nMigrados {len(resultados)} de {len(htmls)} archivos encontrados.")


if __name__ == "__main__":
    main()
