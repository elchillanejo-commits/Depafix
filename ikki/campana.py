"""Integración de Ikki con la generación de afiches y campañas de marketing."""

import os
import uuid

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from supabase import create_client

from ikki.crear_afiche import generar_afiche

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL")

BUCKET_AFICHES = "afiches"

TIPOS_VALIDOS = {"constructores", "abogados", "traders"}

COLORES_POR_TIPO = {
    "constructores": {"fondo": "#1E3A5F", "acento": "#FFC857"},
    "abogados": {"fondo": "#1F2A24", "acento": "#C9A94D"},
    "traders": {"fondo": "#0D1B2A", "acento": "#2ECC71"},
}


def _cliente_supabase():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY no configurados")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def subir_afiche(ruta_local):
    client = _cliente_supabase()
    nombre_remoto = os.path.basename(ruta_local)
    with open(ruta_local, "rb") as f:
        client.storage.from_(BUCKET_AFICHES).upload(
            nombre_remoto,
            f.read(),
            {"content-type": "image/png"},
        )
    return client.storage.from_(BUCKET_AFICHES).get_public_url(nombre_remoto)


def _guardar_campana(tipo, titulo, url_afiche):
    if not SUPABASE_DB_URL:
        raise RuntimeError("SUPABASE_DB_URL no configurado")
    conn = psycopg2.connect(SUPABASE_DB_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    create table if not exists campanas (
                        id uuid primary key default gen_random_uuid(),
                        tipo text not null,
                        titulo text not null,
                        url_afiche text not null,
                        created_at timestamptz not null default now()
                    )
                    """
                )
                cur.execute(
                    """
                    insert into campanas (id, tipo, titulo, url_afiche)
                    values (%(id)s, %(tipo)s, %(titulo)s, %(url_afiche)s)
                    returning id, tipo, titulo, url_afiche, created_at
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "tipo": tipo,
                        "titulo": titulo,
                        "url_afiche": url_afiche,
                    },
                )
                return cur.fetchone()
    finally:
        conn.close()


def crear_campana(tipo, datos):
    """
    Crea una campaña de marketing para Ikki.

    - tipo: "constructores" | "abogados" | "traders"
    - datos: dict con titulo, subtitulo, precio (y opcionalmente logo, imagen_fondo, colores)

    Genera el afiche, lo sube a Supabase Storage (bucket "afiches") y guarda
    el registro en la tabla "campanas". Retorna el registro insertado
    (incluye url_afiche pública).
    """
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"tipo inválido: {tipo!r}. Debe ser uno de {sorted(TIPOS_VALIDOS)}")

    colores = dict(COLORES_POR_TIPO.get(tipo, {}))
    colores.update(datos.get("colores") or {})

    datos_afiche = dict(datos)
    datos_afiche["colores"] = colores
    datos_afiche.setdefault("logo", "circulo")

    ruta_local = generar_afiche(datos_afiche)
    url_afiche = subir_afiche(ruta_local)
    registro = _guardar_campana(tipo, datos.get("titulo", ""), url_afiche)

    return {
        "id": str(registro["id"]),
        "tipo": registro["tipo"],
        "titulo": registro["titulo"],
        "url_afiche": registro["url_afiche"],
        "created_at": registro["created_at"].isoformat(),
    }
