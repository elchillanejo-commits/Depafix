"""
ingestar_videos.py — Handoff 006.
Lee las transcripciones .txt de data/nuevos_videos/, las divide en chunks de
~700 palabras (chunk padre, va a knowledge_entries en Supabase) y cada chunk en
sub-fragmentos de ~150 palabras (van a data/conocimiento.faiss, apuntando a su
padre por parent_id).

El índice FAISS y la tabla knowledge_chunks (pgvector, ver
07_IKKI_MARKETING/sql/09_pgvector_knowledge_chunks.sql) se reconstruyen completos
en cada --apply a partir de TODAS las filas fuente='video_txt' de Supabase, así
quedan siempre alineados con la nube.

Modelo: intfloat/multilingual-e5-small (384d, 512 tokens, multilingüe).
Al consultar el índice hay que codificar la pregunta como "query: <texto>"
con normalize_embeddings=True (ver data/conocimiento.faiss.json).

Por defecto corre en DRY-RUN (no escribe nada). Para escribir: --apply
"""
import os
import re
import sys
import glob
import json
import shutil
import sqlite3
import hashlib
import logging
import argparse
import unicodedata
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(".env")
log = logging.getLogger(__name__)

VIDEOS_DIR = "data/nuevos_videos"
FAISS_PATH = "data/conocimiento.faiss"
FAISS_META_PATH = "data/conocimiento.faiss.json"
DB_PATH = "data/conocimiento.db"  # tabla 'documentos': texto de cada vector FAISS
MODELO = "intfloat/multilingual-e5-small"
PREFIJO_PASAJE = "passage: "
PREFIJO_QUERY = "query: "
FUENTE = "video_txt"
TABLA_CHUNKS = "knowledge_chunks"

PALABRAS_OBJETIVO = 700
PALABRAS_MAX = 1000
SUB_PALABRAS = 150
SUB_SOLAPE = 25

# Orden importa: la primera regla que calza gana.
REGLAS_CATEGORIA = [
    ("Pricing_Agencia", ["cobrar", "precio", "fee", "tarifa", "iva"]),
    ("Google_Ads_CPC", ["cpc", "costo por clic", "costo por click"]),
    ("Estrategia_General", [" vs ", "diferencias", "cual es mejor", "meta y google"]),
    ("Google_Ads_Estructura", ["google ads", "google"]),
    ("Meta_Ads_Estructura", ["meta ads", "facebook", "instagram", "meta"]),
]

CONSULTAS_PRUEBA = [
    "¿Cuánto debería cobrar una agencia por manejar campañas de Meta Ads?",
    "¿Cómo bajo el costo por clic en Google Ads?",
    "¿Conviene más Google o Meta para un negocio local?",
    "¿Cómo estructuro campañas, conjuntos de anuncios y anuncios en Meta?",
]


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def titulo_desde_archivo(path: str) -> str:
    nombre = os.path.splitext(os.path.basename(path))[0]
    nombre = re.sub(r"\[(Spanish \(auto-generated\)|DownSub\.com)\]", "", nombre)
    nombre = re.sub(r"[^\w\s¿?¡!().,:\-ºª$]", "", nombre)  # emojis
    return re.sub(r"\s+", " ", nombre).strip(" -")


def categorizar(titulo: str) -> str:
    t = f" {normalizar(titulo)} "
    for categoria, claves in REGLAS_CATEGORIA:
        if any(clave in t for clave in claves):
            return categoria
    return "Estrategia_General"


def limpiar_transcripcion(texto: str) -> str:
    texto = re.sub(r"\[(música|music|aplausos|risas)\]", " ", texto, flags=re.I)
    return re.sub(r"\s+", " ", texto).strip()


def dividir_en_chunks(texto: str) -> list[str]:
    """Agrupa oraciones hasta ~PALABRAS_OBJETIVO palabras, sin pasar PALABRAS_MAX."""
    oraciones = re.split(r"(?<=[.?!])\s+", texto)
    chunks, actual, n = [], [], 0
    for oracion in oraciones:
        palabras = oracion.split()
        # Oración gigante (transcripción sin puntuación): cortarla a la fuerza
        while len(palabras) > PALABRAS_MAX:
            if actual:
                chunks.append(" ".join(actual))
                actual, n = [], 0
            chunks.append(" ".join(palabras[:PALABRAS_OBJETIVO]))
            palabras = palabras[PALABRAS_OBJETIVO:]
        if n + len(palabras) > PALABRAS_MAX or n >= PALABRAS_OBJETIVO:
            chunks.append(" ".join(actual))
            actual, n = [], 0
        actual.extend(palabras)
        n += len(palabras)
    if actual:
        # Cola muy corta: pegarla al chunk anterior si cabe
        if chunks and n < 200 and len(chunks[-1].split()) + n <= PALABRAS_MAX:
            chunks[-1] += " " + " ".join(actual)
        else:
            chunks.append(" ".join(actual))
    return chunks


def dividir_en_subfragmentos(texto: str) -> list[str]:
    """Ventanas de SUB_PALABRAS con SUB_SOLAPE de solape; la cola corta se pega a la anterior."""
    palabras = texto.split()
    paso = SUB_PALABRAS - SUB_SOLAPE
    ventanas = []
    for inicio in range(0, len(palabras), paso):
        ventanas.append(palabras[inicio:inicio + SUB_PALABRAS])
        if inicio + SUB_PALABRAS >= len(palabras):
            break
    if len(ventanas) > 1 and len(ventanas[-1]) < SUB_PALABRAS // 3:
        ultima = ventanas.pop()
        ventanas[-1] = ventanas[-1] + ultima[SUB_SOLAPE:]
    return [" ".join(v) for v in ventanas]


def construir_chunks() -> list[dict]:
    archivos = sorted(glob.glob(os.path.join(VIDEOS_DIR, "*.txt")))
    if not archivos:
        log.warning(f"No hay .txt en {VIDEOS_DIR}")
    registros = []
    for path in archivos:
        with open(path, "r", encoding="utf-8") as f:
            texto = limpiar_transcripcion(f.read())
        titulo = titulo_desde_archivo(path)
        categoria = categorizar(titulo)
        partes = dividir_en_chunks(texto)
        for i, chunk in enumerate(partes, 1):
            registros.append({
                "archivo": os.path.basename(path),
                "titulo": titulo,
                "categoria": categoria,
                "chunk_index": i,
                "total_chunks": len(partes),
                "palabras": len(chunk.split()),
                "contenido": chunk,
                "chunk_hash": hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:16],
            })
    return registros


def leer_meta(fila: dict) -> dict:
    meta = fila.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            meta = {}
    return meta


def padres_en_supabase(client) -> list[dict]:
    filas = (client.table("knowledge_entries").select("id, titulo, contenido, metadata")
             .eq("fuente", FUENTE).order("id").execute().data)
    padres = []
    for fila in filas:
        meta = leer_meta(fila)
        padres.append({
            "parent_id": fila["id"],
            "titulo": meta.get("titulo") or fila["titulo"],
            "categoria": meta.get("categoria"),
            "archivo": meta.get("archivo"),
            "chunk_index": meta.get("chunk_index"),
            "chunk_hash": meta.get("chunk_hash"),
            "contenido": fila["contenido"],
        })
    return padres


def fila_supabase(r: dict, ahora: str) -> dict:
    return {
        "fuente": FUENTE,
        "url": None,
        "titulo": f"{r['titulo']} [{r['chunk_index']}/{r['total_chunks']}]",
        "contenido": r["contenido"],
        # resumen no nulo para que procesar_conocimiento.py (mock) no lo pise
        "resumen": f"[{r['categoria']}] {r['titulo']} — fragmento {r['chunk_index']}/{r['total_chunks']}",
        "palabras_clave": [r["categoria"]],
        "fecha_extraccion": ahora,
        "metadata": {k: r[k] for k in ("titulo", "archivo", "categoria", "chunk_index",
                                       "total_chunks", "palabras", "chunk_hash")},
    }


def construir_subfragmentos(padres: list[dict]) -> list[dict]:
    subs = []
    for p in padres:
        for j, texto in enumerate(dividir_en_subfragmentos(p["contenido"]), 1):
            subs.append({
                "faiss_id": len(subs),
                "parent_id": p["parent_id"],
                "chunk_hash": p["chunk_hash"],
                "categoria": p["categoria"],
                "titulo": p["titulo"],
                "archivo": p["archivo"],
                "sub_index": j,
                "texto": texto,
            })
    return subs


def cargar_modelo():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODELO)


def construir_indice(modelo, subs: list[dict]):
    import faiss
    emb = modelo.encode([PREFIJO_PASAJE + s["texto"] for s in subs],
                        normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    emb = emb.astype("float32")
    index = faiss.IndexFlatIP(emb.shape[1])  # vectores normalizados → producto interno = coseno
    index.add(emb)
    return index, emb


def filas_pgvector(client) -> int | None:
    """Filas actuales en knowledge_chunks, o None si la tabla aún no existe."""
    try:
        return client.table(TABLA_CHUNKS).select("id", count="exact").limit(1).execute().count
    except Exception as e:
        log.debug(f"{TABLA_CHUNKS} no disponible: {e}")
        return None


def sincronizar_pgvector(client, subs: list[dict], emb) -> None:
    """Reemplaza los sub-fragmentos de los padres video_txt en knowledge_chunks."""
    entry_ids = sorted({s["parent_id"] for s in subs})
    for i in range(0, len(entry_ids), 100):
        client.table(TABLA_CHUNKS).delete().in_("entry_id", entry_ids[i:i + 100]).execute()
    filas = [{
        "entry_id": s["parent_id"],
        "sub_index": s["sub_index"],
        "texto": s["texto"],
        "categoria": s["categoria"],
        "modelo": MODELO,
        # pgvector acepta el literal '[x1,x2,...]'
        "embedding": "[" + ",".join(f"{x:.7f}" for x in emb[j]) + "]",
    } for j, s in enumerate(subs)]
    for i in range(0, len(filas), 100):
        client.table(TABLA_CHUNKS).insert(filas[i:i + 100]).execute()
    log.info(f"✅ pgvector: {len(filas)} sub-fragmentos en {TABLA_CHUNKS}")


def probar_busquedas(modelo, index, subs: list[dict]) -> None:
    print("\nPrueba de búsqueda (top 3):")
    q = modelo.encode([PREFIJO_QUERY + c for c in CONSULTAS_PRUEBA],
                      normalize_embeddings=True).astype("float32")
    puntajes, ids = index.search(q, 3)
    for consulta, fila_p, fila_i in zip(CONSULTAS_PRUEBA, puntajes, ids):
        print(f"  ❓ {consulta}")
        for score, i in zip(fila_p, fila_i):
            s = subs[i]
            print(f"     {score:.3f}  {s['categoria']:<22} {s['titulo'][:45]} "
                  f"[chunk {s['chunk_hash'][:6]} sub {s['sub_index']}]")


def guardar_indice(index, subs: list[dict]) -> None:
    import faiss

    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    for path in (FAISS_PATH, DB_PATH, FAISS_META_PATH):
        if os.path.exists(path):
            shutil.copy2(path, f"{path}.bak_{sello}")
            log.info(f"Respaldo: {path}.bak_{sello}")

    faiss.write_index(index, FAISS_PATH)
    con = sqlite3.connect(DB_PATH)
    with con:
        # 'documentos' es el espejo 1:1 del índice (posición FAISS = faiss_id)
        con.execute("DELETE FROM documentos")
        con.executemany(
            "INSERT INTO documentos (text, source, metadata) VALUES (?, ?, ?)",
            [(s["texto"], s["archivo"],
              json.dumps({k: v for k, v in s.items() if k != "texto"}, ensure_ascii=False))
             for s in subs],
        )
    con.close()
    with open(FAISS_META_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "modelo": MODELO,
            "dim": index.d,
            "metrica": "IndexFlatIP (coseno, vectores normalizados)",
            "prefijo_query": PREFIJO_QUERY,
            "prefijo_pasaje": PREFIJO_PASAJE,
            "vectores": index.ntotal,
            "mapeo": "posición FAISS = metadata.faiss_id en conocimiento.db/documentos; "
                     "metadata.parent_id = knowledge_entries.id en Supabase",
            "generado": datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)
    log.info(f"✅ FAISS reconstruido: {index.ntotal} vectores ({FAISS_PATH})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Escribir en Supabase y reconstruir FAISS (sin esto: dry-run)")
    args = parser.parse_args()

    from supabase import create_client
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and key):
        sys.exit("Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY en .env")
    client = create_client(url, key)

    registros = construir_chunks()
    existentes = padres_en_supabase(client)
    hashes = {p["chunk_hash"] for p in existentes}
    nuevos = [r for r in registros if r["chunk_hash"] not in hashes]

    print(f"\n{'APPLY' if args.apply else 'DRY-RUN'} — {len(registros)} chunks padre en {VIDEOS_DIR}")
    print(f"{'video':<62} {'categoría':<22} {'chunks':>6} {'palabras/chunk':>16}")
    for archivo in dict.fromkeys(r["archivo"] for r in registros):
        rs = [r for r in registros if r["archivo"] == archivo]
        tam = [r["palabras"] for r in rs]
        print(f"{rs[0]['titulo'][:60]:<62} {rs[0]['categoria']:<22} {len(rs):>6} {min(tam):>7}–{max(tam):<8}")
    por_cat = {}
    for r in nuevos:
        por_cat[r["categoria"]] = por_cat.get(r["categoria"], 0) + 1
    print(f"\nSupabase knowledge_entries (fuente={FUENTE}): {len(existentes)} ya cargados")
    print(f"NUEVOS chunks padre a insertar: {len(nuevos)}  {por_cat}")

    if args.apply and nuevos:
        ahora = datetime.now().isoformat()
        filas = [fila_supabase(r, ahora) for r in nuevos]
        for i in range(0, len(filas), 50):
            client.table("knowledge_entries").insert(filas[i:i + 50]).execute()
        log.info(f"✅ {len(filas)} filas insertadas en knowledge_entries")
        padres = padres_en_supabase(client)
    else:
        # Dry-run: los nuevos aún no tienen id de Supabase
        padres = existentes + [{**r, "parent_id": None} for r in nuevos]

    subs = construir_subfragmentos(padres)
    if not subs:
        print("Nada que indexar.")
        return
    tam = [len(s["texto"].split()) for s in subs]
    print(f"Sub-fragmentos para FAISS: {len(subs)} ({min(tam)}–{max(tam)} palabras, "
          f"solape {SUB_SOLAPE})")

    modelo = cargar_modelo()
    tokens = max(len(modelo.tokenizer(PREFIJO_PASAJE + s["texto"])["input_ids"]) for s in subs)
    print(f"Modelo: {MODELO} — dim {modelo.get_sentence_embedding_dimension()}, "
          f"máx tokens por sub-fragmento {tokens}/{modelo.max_seq_length}"
          f"{'  ⚠️ TRUNCA' if tokens > modelo.max_seq_length else ''}")
    index, emb = construir_indice(modelo, subs)

    if os.path.exists(FAISS_PATH):
        import faiss
        viejo = faiss.read_index(FAISS_PATH)
        print(f"FAISS actual: {viejo.ntotal} vectores {viejo.d}d → se reemplaza por {index.ntotal} vectores {index.d}d")

    n_pg = filas_pgvector(client)
    if n_pg is None:
        print(f"pgvector: tabla {TABLA_CHUNKS} no existe todavía → se omite "
              "(correr 07_IKKI_MARKETING/sql/09_pgvector_knowledge_chunks.sql)")
    else:
        print(f"pgvector: {TABLA_CHUNKS} {n_pg} filas → {len(subs)}")

    probar_busquedas(modelo, index, subs)

    if args.apply:
        guardar_indice(index, subs)
        if n_pg is not None:
            sincronizar_pgvector(client, subs, emb)
    else:
        print("\n(dry-run: no se escribió nada. Usa --apply para insertar y reconstruir.)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
