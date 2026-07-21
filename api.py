import logging
import os
import uuid

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ikki.campana import TIPOS_VALIDOS, crear_campana, subir_afiche
from ikki.crear_afiche import generar_afiche

load_dotenv()

logger = logging.getLogger("api")

SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL")

app = FastAPI(title="Agente Procurador IA - API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ComprarTokensRequest(BaseModel):
    cliente_id: str
    cantidad: int
    monto: float | None = None
    metodo_pago: str = "mock"


class ConsultarRequest(BaseModel):
    cliente_id: str
    tipo_consulta: str
    detalle: dict = {}


class GenerarAficheRequest(BaseModel):
    titulo: str
    subtitulo: str
    precio: str
    color_fondo: str | None = None


class CampanaRequest(BaseModel):
    tipo: str
    titulo: str
    subtitulo: str | None = None
    precio: str | None = None


@app.get("/api/clientes")
def listar_clientes():
    if not SUPABASE_DB_URL:
        logger.error("SUPABASE_DB_URL no está configurado")
        return JSONResponse(status_code=500, content={"error": "SUPABASE_DB_URL no está configurado"})

    conn = None
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                select id, nombre, rut, estado, fecha_creacion
                from clientes
                order by fecha_creacion desc
                """
            )
            filas = cur.fetchall()
    except psycopg2.OperationalError:
        logger.exception("No se pudo conectar a la base de datos")
        return JSONResponse(status_code=503, content={"error": "No se pudo conectar a la base de datos"})
    except psycopg2.Error:
        logger.exception("Error al consultar clientes")
        return JSONResponse(status_code=500, content={"error": "Error al consultar clientes"})
    finally:
        if conn is not None:
            conn.close()

    return [
        {
            "id": str(fila["id"]),
            "nombre": fila["nombre"],
            "rut": fila["rut"],
            "estado": fila["estado"],
            "fecha_creacion": fila["fecha_creacion"].isoformat() if fila["fecha_creacion"] else None,
        }
        for fila in filas
    ]


@app.get("/api/rubros")
def obtener_rubros():
    if not SUPABASE_DB_URL:
        logger.error("SUPABASE_DB_URL no está configurado")
        return JSONResponse(status_code=500, content={"error": "SUPABASE_DB_URL no está configurado"})

    conn = None
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                select
                    coalesce(rubro, 'Otros') as rubro,
                    count(*) as cantidad_materiales,
                    sum(cantidad * precio_unitario) as costo_total
                from line_items
                group by coalesce(rubro, 'Otros')
                order by costo_total desc
                """
            )
            filas = cur.fetchall()
    except psycopg2.OperationalError:
        logger.exception("No se pudo conectar a la base de datos")
        return JSONResponse(status_code=503, content={"error": "No se pudo conectar a la base de datos"})
    except psycopg2.Error:
        logger.exception("Error al consultar rubros")
        return JSONResponse(status_code=500, content={"error": "Error al consultar rubros"})
    finally:
        if conn is not None:
            conn.close()

    return [
        {
            "rubro": fila["rubro"],
            "cantidad_materiales": fila["cantidad_materiales"],
            "costo_total": float(fila["costo_total"]),
        }
        for fila in filas
    ]


@app.get("/api/decreto49")
def obtener_decreto49():
    """Artículos del D.S. N°49/2011, reusando decretos/decreto_articulos (sql/create_normativa_ds49.sql)."""
    if not SUPABASE_DB_URL:
        logger.error("SUPABASE_DB_URL no está configurado")
        return JSONResponse(status_code=500, content={"error": "SUPABASE_DB_URL no está configurado"})

    conn = None
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                select d.numero as decreto_numero, d.titulo as decreto_titulo,
                       a.numero as articulo, a.contenido
                from decreto_articulos a
                join decretos d on d.id = a.decreto_id
                order by d.numero, a.numero
                """
            )
            filas = cur.fetchall()
    except psycopg2.OperationalError:
        logger.exception("No se pudo conectar a la base de datos")
        return JSONResponse(status_code=503, content={"error": "No se pudo conectar a la base de datos"})
    except psycopg2.Error:
        logger.exception("Error al consultar decreto49")
        return JSONResponse(status_code=500, content={"error": "Error al consultar decreto49"})
    finally:
        if conn is not None:
            conn.close()

    return [
        {
            "decreto": fila["decreto_numero"],
            "decreto_titulo": fila["decreto_titulo"],
            "articulo": fila["articulo"],
            "contenido": fila["contenido"],
        }
        for fila in filas
    ]


def _saldo_cliente(cur, cliente_id: str) -> int:
    cur.execute(
        """
        select coalesce(sum(consultas_restantes), 0) as saldo
        from tokens
        where usuario_id = %(cliente_id)s
          and (fecha_expiracion is null or fecha_expiracion > now())
        """,
        {"cliente_id": cliente_id},
    )
    return cur.fetchone()["saldo"]


@app.get("/api/tokens/saldo")
def obtener_saldo(cliente_id: str):
    if not SUPABASE_DB_URL:
        logger.error("SUPABASE_DB_URL no está configurado")
        return JSONResponse(status_code=500, content={"error": "SUPABASE_DB_URL no está configurado"})

    conn = None
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            saldo = _saldo_cliente(cur, cliente_id)
    except psycopg2.OperationalError:
        logger.exception("No se pudo conectar a la base de datos")
        return JSONResponse(status_code=503, content={"error": "No se pudo conectar a la base de datos"})
    except psycopg2.Error:
        logger.exception("Error al consultar saldo")
        return JSONResponse(status_code=500, content={"error": "Error al consultar saldo"})
    finally:
        if conn is not None:
            conn.close()

    return {"cliente_id": cliente_id, "tokens": saldo}


@app.post("/api/comprar_tokens")
def comprar_tokens(req: ComprarTokensRequest):
    if req.cantidad <= 0:
        return JSONResponse(status_code=400, content={"error": "cantidad debe ser mayor a 0"})

    if not SUPABASE_DB_URL:
        logger.error("SUPABASE_DB_URL no está configurado")
        return JSONResponse(status_code=500, content={"error": "SUPABASE_DB_URL no está configurado"})

    conn = None
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                codigo_token = f"TKN-{uuid.uuid4().hex[:12]}"
                cur.execute(
                    """
                    insert into tokens (usuario_id, codigo_token, consultas_restantes, fecha_compra)
                    values (%(cliente_id)s, %(codigo_token)s, %(cantidad)s, now())
                    returning id, codigo_token, consultas_restantes, fecha_compra
                    """,
                    {
                        "cliente_id": req.cliente_id,
                        "codigo_token": codigo_token,
                        "cantidad": req.cantidad,
                    },
                )
                token = cur.fetchone()

                cur.execute(
                    """
                    insert into compras (cliente_id, token_id, cantidad, monto, metodo_pago)
                    values (%(cliente_id)s, %(token_id)s, %(cantidad)s, %(monto)s, %(metodo_pago)s)
                    returning id, fecha_compra
                    """,
                    {
                        "cliente_id": req.cliente_id,
                        "token_id": token["id"],
                        "cantidad": req.cantidad,
                        "monto": req.monto,
                        "metodo_pago": req.metodo_pago,
                    },
                )
                compra = cur.fetchone()
                saldo = _saldo_cliente(cur, req.cliente_id)
    except psycopg2.errors.ForeignKeyViolation:
        logger.exception("cliente_id inexistente al comprar tokens")
        return JSONResponse(status_code=404, content={"error": "cliente_id no existe"})
    except psycopg2.OperationalError:
        logger.exception("No se pudo conectar a la base de datos")
        return JSONResponse(status_code=503, content={"error": "No se pudo conectar a la base de datos"})
    except psycopg2.Error:
        logger.exception("Error al registrar compra de tokens")
        return JSONResponse(status_code=500, content={"error": "Error al registrar compra de tokens"})
    finally:
        if conn is not None:
            conn.close()

    return {
        "ok": True,
        "token": {
            "id": str(token["id"]),
            "codigo_token": token["codigo_token"],
            "consultas_restantes": token["consultas_restantes"],
        },
        "compra": {"id": str(compra["id"]), "fecha_compra": compra["fecha_compra"].isoformat()},
        "saldo_actual": saldo,
    }


@app.post("/api/consultar")
def consultar(req: ConsultarRequest):
    if not SUPABASE_DB_URL:
        logger.error("SUPABASE_DB_URL no está configurado")
        return JSONResponse(status_code=500, content={"error": "SUPABASE_DB_URL no está configurado"})

    conn = None
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("select 1 from clientes where id = %(cliente_id)s", {"cliente_id": req.cliente_id})
                if cur.fetchone() is None:
                    return JSONResponse(status_code=404, content={"error": "cliente_id no existe"})

                cur.execute(
                    """
                    select id
                    from tokens
                    where usuario_id = %(cliente_id)s
                      and consultas_restantes > 0
                      and (fecha_expiracion is null or fecha_expiracion > now())
                    order by fecha_compra asc nulls last
                    limit 1
                    for update
                    """,
                    {"cliente_id": req.cliente_id},
                )
                token = cur.fetchone()
                if token is None:
                    return JSONResponse(status_code=402, content={"error": "tokens insuficientes"})

                cur.execute(
                    "update tokens set consultas_restantes = consultas_restantes - 1 where id = %(id)s",
                    {"id": token["id"]},
                )

                cur.execute(
                    """
                    insert into consultas (cliente_id, tipo_consulta, detalle, token_usado)
                    values (%(cliente_id)s, %(tipo_consulta)s, %(detalle)s, 1)
                    returning id, fecha_consulta
                    """,
                    {
                        "cliente_id": req.cliente_id,
                        "tipo_consulta": req.tipo_consulta,
                        "detalle": psycopg2.extras.Json(req.detalle),
                    },
                )
                consulta = cur.fetchone()
                saldo = _saldo_cliente(cur, req.cliente_id)
    except psycopg2.errors.ForeignKeyViolation:
        logger.exception("cliente_id inexistente al consultar")
        return JSONResponse(status_code=404, content={"error": "cliente_id no existe"})
    except psycopg2.OperationalError:
        logger.exception("No se pudo conectar a la base de datos")
        return JSONResponse(status_code=503, content={"error": "No se pudo conectar a la base de datos"})
    except psycopg2.Error:
        logger.exception("Error al registrar consulta")
        return JSONResponse(status_code=500, content={"error": "Error al registrar consulta"})
    finally:
        if conn is not None:
            conn.close()

    return {
        "ok": True,
        "consulta": {"id": str(consulta["id"]), "fecha_consulta": consulta["fecha_consulta"].isoformat()},
        "saldo_restante": saldo,
    }


@app.post("/api/generar_afiche")
def generar_afiche_endpoint(req: GenerarAficheRequest):
    if not req.titulo.strip() or not req.subtitulo.strip() or not req.precio.strip():
        return JSONResponse(
            status_code=400, content={"error": "titulo, subtitulo y precio son requeridos"}
        )

    try:
        datos = {"titulo": req.titulo, "subtitulo": req.subtitulo, "precio": req.precio}
        if req.color_fondo:
            datos["colores"] = {"fondo": req.color_fondo}

        ruta_local = generar_afiche(datos)

        try:
            url = subir_afiche(ruta_local)
            return {"ok": True, "url": url}
        except Exception:
            logger.exception("No se pudo subir el afiche a Supabase Storage")
            return {"ok": True, "ruta_local": ruta_local}
    except Exception as e:
        logger.exception("Error generando afiche")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/campana/crear")
def crear_campana_endpoint(req: CampanaRequest):
    if req.tipo not in TIPOS_VALIDOS:
        return JSONResponse(
            status_code=400,
            content={"error": f"tipo inválido: {req.tipo!r}. Debe ser uno de {sorted(TIPOS_VALIDOS)}"},
        )

    try:
        datos = {"titulo": req.titulo, "subtitulo": req.subtitulo, "precio": req.precio}
        resultado = crear_campana(req.tipo, datos)
        return {"ok": True, **resultado}
    except Exception as e:
        logger.exception("Error creando campaña")
        return JSONResponse(status_code=500, content={"error": str(e)})
