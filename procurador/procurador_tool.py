#!/usr/bin/env python3
"""
procurador_tool.py -- Pipeline del nodo Procurador: extrae datos
judiciales de PDFs chilenos (ROL, tribunal, etapa procesal, litigantes,
proximo plazo), evalua riesgo contra config/legal_rules.json y persiste
el dictamen en compliance_logs.

Schema REAL de compliance_logs en Supabase (verificado en vivo):
    id, rol, etapa_procesal, riesgo_detectado, dictamen, metadata, created_at
No hay columnas propias para tribunal/litigantes/proximo_plazo/
idempotency_key -- todo eso vive dentro de metadata (JSONB).

Modos (CLI):
  parse <pdf>       -> parsear un PDF y guardar en compliance_logs
  cron               -> actualizar todos los ROLes activos con novedades del tribunal (placeholder)
  batch <carpeta>    -> procesar UNA VEZ los PDFs pendientes en una carpeta y salir (sin loop infinito)
"""
import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pdfplumber

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.resiliencia import red_segura, RedFailSafeError

# NOTA: DatabaseManager se importa de forma perezosa (dentro de cada
# funcion que lo usa) en vez de aca arriba. core/db_manager.py crea un
# singleton a nivel de modulo (`db_manager = DatabaseManager()`) que exige
# SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY en el entorno -- si se importara
# aca arriba, ni siquiera dry_run_parse() podria correr sin credenciales,
# pese a que nunca toca Supabase.

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Regex judiciales
# --------------------------------------------------------------------------- #
ROL_PATTERN = re.compile(r'ROL\s*[Nn]?°?\s*([CRD]\s*-\s*\d+\s*-\s*\d{4})', re.IGNORECASE)
TRIBUNAL_PATTERN = re.compile(r'(?:\bante\b|tribunal|juzgado|j\.)\s*:?\s*(.{5,80}?)(?:\.|,|ROL|En|Vistos)', re.IGNORECASE | re.DOTALL)

# Etapas intermedias -- se busca la ULTIMA que aparece en el texto (no la
# primera), porque un expediente narra su historia completa y la mencion
# mas tardia es la que refleja el estado actual real del caso.
ETAPA_PATTERNS = [
    ("discusión", re.compile(r'(discusión|demanda|contestación|réplica|dúplica)', re.IGNORECASE)),
    ("prueba", re.compile(r'(término probatorio|audiencia de prueba|prueba pericial)', re.IGNORECASE)),
    ("apelación", re.compile(r'(recurso de apelaci[oó]n|en apelaci[oó]n|apelad[oa])', re.IGNORECASE)),
    ("sentencia", re.compile(r'(sentencia|fallo|laudo)', re.IGNORECASE)),
    ("ejecución", re.compile(r'(ejecución|mandamiento de pago|embargo)', re.IGNORECASE)),
]
# "Firme y ejecutoriada" es un estado terminal inequivoco (no hay mas
# recursos posibles) -- tiene prioridad semantica sobre cualquier otra
# etapa detectada por posicion, no solo por aparecer al final del texto.
ETAPA_FIRME_PATTERN = re.compile(r'firme\s+y\s+ejecutoriada', re.IGNORECASE)

# Encabezado del sistema de tramitacion del Poder Judicial ("Etapa: X
# Estado Procesal: Y"): cuando esta presente es la fuente de verdad de
# la etapa actual, mas confiable que el heuristico de ultima mencion
# -- ese heuristico se confunde con alegatos que discuten una etapa
# (p.ej. "requiere periodo de prueba amplio") sin que el caso este
# realmente en esa etapa.
ETAPA_HEADER_PATTERN = re.compile(r'Etapa:\s*([^\n]+?)\s+Estado\s+Procesal:', re.IGNORECASE)

# Patron estructurado: en los expedientes del Poder Judicial chileno la
# tabla de litigantes usa filas "<CODIGO>. <RUT> <NATURAL|JURIDICA> <nombre>"
# donde DTE./DDO. son las partes y AB.DTE/AP.DTE/AB.DDO/AP.DDO son sus
# abogados/apoderados -- mezclarlos fue el bug original (capturaba el
# nombre del apoderado en vez de la parte). El \b antes de DTE\./DDO\.
# mas el hecho de que "AB.DTE"/"AP.DTE" no contienen el punto pegado a
# "DTE" evita que el patron de la parte matchee esas filas de abogados.
# Ademas de las filas de tabla y "Tabla de contenidos", una fila DTE./DDO.
# aislada (fuera de la tabla completa de Litigantes) puede aparecer en un
# bloque resumen al inicio del documento, pegada directamente al bloque de
# metadata del expediente (ROL/Caratulado) sin otra fila DTE./DDO. cerca --
# sin cortar ahi tambien, la captura se comia esa metadata completa hasta
# la proxima fila real, muy mas adelante en el documento.
LITIGANTE_DTE_TABLA_PATTERN = re.compile(
    r'\bDTE\.\s*[\dKk\-]+\s*(?:NATURAL|JURIDICA)\s+(.+?)(?=\n(?:AB\.|AP\.|DTE\.|DDO\.)|\nTabla|\nROL\s*:|\nCaratulado\s*:|\Z)',
    re.IGNORECASE | re.DOTALL,
)
LITIGANTE_DDO_TABLA_PATTERN = re.compile(
    r'\bDDO\.\s*[\dKk\-]+\s*(?:NATURAL|JURIDICA)\s+(.+?)(?=\n(?:AB\.|AP\.|DTE\.|DDO\.)|\nTabla|\nROL\s*:|\nCaratulado\s*:|\Z)',
    re.IGNORECASE | re.DOTALL,
)
# Fallback en prosa -- para documentos que no traen la tabla estructurada
# del Poder Judicial (ej. contratos, escritos sueltos). Se detiene antes
# de metadata de representacion ("FOLIO DESIGNACIÓN", "TIPO DE PODER") que
# es lo que hacia que el regex original se comiera texto ajeno al nombre.
LITIGANTES_DEM_PATTERN = re.compile(
    r'(?:demandante|actor|recurrente|querellante)\s*:\s*(.{1,200}?)'
    r'(?=\s*(?:demandado|recurrido|querellado)\s*:'
    r'|\s*FOLIO\s+DESIGNACIÓN'
    r'|\s*TIPO\s+DE\s+PODER'
    # En prosa simple (una parte por linea) "Ante"/"ROL" en la linea
    # siguiente marcan el salto al tribunal, no siguen siendo el nombre --
    # sin este corte, si "demandado:" ya aparecio ANTES que "demandante:"
    # en el texto (orden invertido, valido en algunos escritos), no queda
    # ningun limite antes del fin del documento y se traga todo lo que sigue.
    r'|\n\s*(?:ante\b|rol\b)'
    r'|\n\n|\Z)',
    re.IGNORECASE | re.DOTALL,
)
# Sin DOTALL: "." no cruza saltos de linea, asi que el lookahead puede
# pedir "\n" como limite ademas de "." o fin de string -- la version
# anterior exigia consumir un "." o llegar al fin absoluto del string,
# y fallaba en silencio (sin match, sin campo "demandado") cuando el
# valor terminaba en salto de linea sin punto final.
LITIGANTES_DDO_PATTERN = re.compile(r'(?:demandado|recurrido|querellado)\s*:\s*(.+?)(?=\.|\n|$)', re.IGNORECASE)

# Fechas -- se extraen TODAS las que aparecen en el documento (no la
# primera que matchea "proximo plazo:", que casi nunca aparece asi
# literalmente en un expediente real) y se filtran las posteriores a hoy;
# la mas cercana al presente es el "proximo plazo" real. Si no hay ninguna
# futura (caso ya cerrado, por ejemplo firme y ejecutoriada), no hay plazo
# que reportar y el campo debe quedar en None -- no es un fallo del parser.
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
FECHA_DDMMYYYY_PATTERN = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b')
FECHA_TEXTO_PATTERN = re.compile(
    r'(\d{1,2})\s*(?:de\s*)?(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s*(?:de\s*)?(\d{4})',
    re.IGNORECASE,
)

LEGAL_RULES_PATH = REPO_ROOT / "config" / "legal_rules.json"
FALLBACK_JSONL = REPO_ROOT / "compliance_logs_pendientes.jsonl"


# --------------------------------------------------------------------------- #
# RobustPDFExtractor
# --------------------------------------------------------------------------- #
class RobustPDFExtractor:
    """Extrae texto de un PDF judicial tolerando encoding raro y paginas sin
    texto plano. Reintenta la lectura un par de veces por si el PDF
    todavia se esta escribiendo a disco (caso tipico de un batch que
    corre justo cuando otro proceso deja caer un archivo)."""

    def __init__(self, pdf_path, retries=3, retry_wait=1.0):
        self.pdf_path = str(pdf_path)
        self.retries = retries
        self.retry_wait = retry_wait
        self.text = self._extract_text_with_retry()

    def _extract_page_text(self, page):
        text = page.extract_text()
        if text:
            return text
        words = page.extract_words()
        return " ".join(w["text"] for w in words) if words else ""

    def _extract_tables_text(self, page):
        chunks = []
        try:
            for table in page.extract_tables():
                for row in table:
                    cells = [c for c in row if c]
                    if cells:
                        chunks.append(" ".join(cells))
        except Exception:
            pass
        return "\n".join(chunks)

    def _read_pdf(self):
        parts = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                parts.append(self._extract_page_text(page))
                table_text = self._extract_tables_text(page)
                if table_text:
                    parts.append(table_text)
        return unicodedata.normalize("NFC", "\n".join(parts))

    def _extract_text_with_retry(self):
        last_err = None
        for intento in range(1, self.retries + 1):
            try:
                return self._read_pdf()
            except Exception as e:
                last_err = e
                logger.warning("Lectura de %s fallo (intento %d/%d): %s", self.pdf_path, intento, self.retries, e)
                if intento < self.retries:
                    time.sleep(self.retry_wait)
        raise RuntimeError(f"No se pudo leer {self.pdf_path} tras {self.retries} intentos") from last_err


# --------------------------------------------------------------------------- #
# ProcuradorParser -- regex sobre texto ya extraido
# --------------------------------------------------------------------------- #
class ProcuradorParser:
    def __init__(self, text):
        self.text = text

    @classmethod
    def from_pdf(cls, pdf_path):
        return cls(RobustPDFExtractor(pdf_path).text)

    @staticmethod
    def _limpiar(valor):
        """Colapsa saltos de linea/espacios multiples de un VALOR YA
        CAPTURADO (no del texto crudo completo -- extract_litigantes y
        extract_etapa dependen de los '\\n' del texto crudo para ubicar
        limites de fila/orden cronologico, asi que normalizar todo el
        documento de entrada rompería esa logica)."""
        return re.sub(r'\s+', ' ', valor).strip()

    def extract_rol(self):
        m = ROL_PATTERN.search(self.text)
        return self._limpiar(m.group(1)).upper().replace(" ", "") if m else None

    def extract_tribunal(self):
        m = TRIBUNAL_PATTERN.search(self.text)
        return self._limpiar(m.group(1))[:80] if m else None

    def extract_etapa(self):
        """Devuelve la etapa procesal ACTUAL: "Sentencia firme" si el
        documento contiene "firme y ejecutoriada" (estado terminal, tiene
        prioridad semantica sobre cualquier otra cosa detectada); si no,
        el campo "Etapa: X" del encabezado de tramitacion del Poder
        Judicial si esta presente (fuente de verdad); si no, la ultima
        etapa mencionada en el texto (no la primera -- un expediente
        narra su historia completa en orden, y la mencion mas tardia es
        la que refleja el estado real hoy). "Desconocida" si no se
        encuentra ninguna etapa."""
        if ETAPA_FIRME_PATTERN.search(self.text):
            return "Sentencia firme"
        m = ETAPA_HEADER_PATTERN.search(self.text)
        if m:
            return self._limpiar(m.group(1))
        ultima_etapa, ultima_pos = None, -1
        for etapa, pat in ETAPA_PATTERNS:
            for m in pat.finditer(self.text):
                if m.start() > ultima_pos:
                    ultima_pos, ultima_etapa = m.start(), etapa
        return ultima_etapa or "Desconocida"

    def extract_litigantes(self):
        lit = {}
        m = LITIGANTE_DTE_TABLA_PATTERN.search(self.text) or LITIGANTES_DEM_PATTERN.search(self.text)
        if m:
            lit["demandante"] = self._limpiar(m.group(1))[:100]
        m = LITIGANTE_DDO_TABLA_PATTERN.search(self.text) or LITIGANTES_DDO_PATTERN.search(self.text)
        if m:
            lit["demandado"] = self._limpiar(m.group(1))[:100]
        return lit

    def _fechas_encontradas(self):
        fechas = []
        for d, mth, y in FECHA_DDMMYYYY_PATTERN.findall(self.text):
            try:
                fechas.append(datetime(int(y), int(mth), int(d)))
            except ValueError:
                continue
        for d, mes_nombre, y in FECHA_TEXTO_PATTERN.findall(self.text):
            mes = MESES.get(mes_nombre.lower())
            if not mes:
                continue
            try:
                fechas.append(datetime(int(y), mes, int(d)))
            except ValueError:
                continue
        return fechas

    def extract_proximo_plazo(self):
        """Entre TODAS las fechas del documento, la mas cercana en el
        futuro respecto de hoy. None si no hay ninguna futura (tipico de
        un caso ya cerrado) -- eso es el resultado correcto, no un fallo."""
        futuras = [f for f in self._fechas_encontradas() if f > datetime.now()]
        return min(futuras).strftime("%d/%m/%Y") if futuras else None

    def parse(self):
        return {
            "rol": self.extract_rol(),
            "tribunal": self.extract_tribunal(),
            "etapa_procesal": self.extract_etapa(),
            "litigantes": self.extract_litigantes(),
            "proximo_plazo": self.extract_proximo_plazo(),
        }


# --------------------------------------------------------------------------- #
# Motor de riesgo -- reglas contra config/legal_rules.json (sin LLM)
# --------------------------------------------------------------------------- #
def _cargar_legal_rules(path=LEGAL_RULES_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_legal_risk(parsed_data, raw_text, rules_path=LEGAL_RULES_PATH):
    """Motor basado en reglas (sin LLM). Devuelve riesgos detectados,
    risk_score acumulado, dictamen_final y las clausulas de salvaguarda
    (si alguna regla de tipo clausula_abusiva disparo)."""
    config = _cargar_legal_rules(rules_path)
    pesos = config.get("severidad_peso", {"alto": 3, "medio": 2, "bajo": 1})
    campos = dict(parsed_data)
    campos["raw_text"] = raw_text

    riesgos = []
    safeguard_clauses = []
    for regla in config.get("reglas", []):
        campo = regla["campo"]
        valor_campo = campos.get(campo)
        tipo = regla["tipo"]
        disparado = False

        if tipo == "campo_requerido":
            disparado = valor_campo in (None, "", {}, [])
        elif tipo == "keyword_presente":
            texto = valor_campo if isinstance(valor_campo, str) else raw_text
            texto_lower = (texto or "").lower()
            disparado = any(kw.lower() in texto_lower for kw in regla.get("valor", []))
        elif tipo == "regex_match":
            texto = valor_campo if isinstance(valor_campo, str) else raw_text
            disparado = bool(re.search(regla.get("valor", ""), texto or "", re.IGNORECASE))
        elif tipo == "clausula_abusiva":
            texto = valor_campo if isinstance(valor_campo, str) else raw_text
            texto_lower = (texto or "").lower()
            disparado = any(kw.lower() in texto_lower for kw in regla.get("valor", []))
            if disparado and regla.get("salvaguarda"):
                safeguard_clauses.append({"id": regla["id"], "salvaguarda": regla["salvaguarda"]})

        if disparado:
            riesgos.append({"id": regla["id"], "severidad": regla["severidad"], "mensaje": regla["mensaje"]})

    risk_score = sum(pesos.get(r["severidad"], 0) for r in riesgos)
    severidades = {r["severidad"] for r in riesgos}
    if "abusiva" in severidades:
        dictamen_final = "NEGOCIAR"
    elif "alto" in severidades:
        dictamen_final = "REVISION_URGENTE"
    elif "medio" in severidades:
        dictamen_final = "REVISION_MANUAL"
    elif "bajo" in severidades:
        dictamen_final = "OBSERVACION_MENOR"
    else:
        dictamen_final = "SIN_OBSERVACIONES"

    return {
        "riesgos": riesgos,
        "risk_score": risk_score,
        "dictamen_final": dictamen_final,
        "safeguard_clauses": safeguard_clauses,
    }


# --------------------------------------------------------------------------- #
# Persistencia Supabase -- schema real, service_role, reintentos
# --------------------------------------------------------------------------- #
@red_segura()
def _insert_compliance_log(sp, payload):
    return sp.table("compliance_logs").insert(payload).execute()


@red_segura()
def _insert_error_log(sp, payload):
    return sp.table("error_logs").insert(payload).execute()


def _log_error(funcion, mensaje, metadata=None):
    """Registra un fallo en error_logs (schema real: modulo/funcion/
    mensaje/stack_trace/metadata). Si tambien falla, cae a un JSONL local
    para no perder la notificacion del fallo."""
    fila = {
        "modulo": "procurador_tool",
        "funcion": funcion,
        "mensaje": str(mensaje)[:2000],
        "metadata": metadata or {},
    }
    try:
        from core.db_manager import DatabaseManager
        sp = DatabaseManager().get_service_client()
        _insert_error_log(sp, fila)
        logger.info("Error registrado en error_logs: %s", funcion)
    except Exception as e:
        logger.error("No se pudo registrar en error_logs (%s). Guardando fallback local.", e)
        try:
            with open(FALLBACK_JSONL, "a", encoding="utf-8") as f:
                f.write(json.dumps({"tipo": "error_log", **fila}, ensure_ascii=False) + "\n")
        except Exception:
            logger.critical("No se pudo guardar ni el fallback local del error: %s", fila)


def _procesar_pdf(pdf_path):
    """Extrae texto, parsea campos judiciales y evalua riesgo -- sin tocar
    Supabase. Aislado para poder reusarse tanto en el pipeline real
    (save_parsed_to_compliance) como en dry_run_parse (que nunca debe
    necesitar credenciales)."""
    extractor = RobustPDFExtractor(pdf_path)
    data = ProcuradorParser(extractor.text).parse()
    if not data["rol"]:
        raise ValueError(f"No se pudo identificar el ROL en {pdf_path}")
    riesgo = analyze_legal_risk(data, extractor.text)
    return data, riesgo, extractor


def _construir_payload(data, riesgo, extractor, tiempo_ms, firm_id=None):
    doc_hash = hashlib.sha256(extractor.text.encode()).hexdigest()
    idem_key = hashlib.sha256(f"procurador_{data['rol']}_{doc_hash}".encode()).hexdigest()
    riesgo_detectado = "; ".join(r["mensaje"] for r in riesgo["riesgos"]) or "Sin riesgos detectados"
    return idem_key, {
        "rol": data["rol"],
        "etapa_procesal": data["etapa_procesal"],
        "riesgo_detectado": riesgo_detectado,
        "dictamen": riesgo["dictamen_final"],
        "metadata": {
            "tribunal": data["tribunal"],
            "litigantes": data["litigantes"],
            "proximo_plazo": data["proximo_plazo"],
            "document_hash": doc_hash,
            "idempotency_key": idem_key,
            "risk_score": riesgo["risk_score"],
            "critical_risks": riesgo["riesgos"],
            "safeguard_clauses": riesgo["safeguard_clauses"],
            "firm_id": firm_id,
            "tiempo_procesamiento_ms": tiempo_ms,
            "archivo_origen": str(extractor.pdf_path),
        },
    }


def dry_run_parse(pdf_path):
    """Corre extraccion + parsing + motor de riesgo y muestra el payload
    que se insertaria en compliance_logs -- SIN llamar a Supabase en
    ningun momento (ni siquiera para error_logs). No requiere
    SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY configuradas."""
    inicio = time.perf_counter()
    data, riesgo, extractor = _procesar_pdf(pdf_path)
    tiempo_ms = round((time.perf_counter() - inicio) * 1000, 1)
    _, payload = _construir_payload(data, riesgo, extractor, tiempo_ms)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    logger.info("[DRY-RUN] No se escribio en Supabase -- el JSON de arriba es lo que se insertaria en compliance_logs.")
    return payload


def save_parsed_to_compliance(pdf_path, firm_id=None):
    """Parsea un PDF, evalua riesgo y lo guarda en compliance_logs.
    Devuelve el id de la fila (nueva o ya existente por idempotencia) o
    None si fallo."""
    inicio = time.perf_counter()
    try:
        data, riesgo, extractor = _procesar_pdf(pdf_path)
    except ValueError as e:
        logger.warning(str(e))
        _log_error("rol_no_encontrado", str(e), {"archivo": str(pdf_path)})
        return None
    except Exception as e:
        _log_error("extraccion_pdf", e, {"archivo": str(pdf_path)})
        return None

    tiempo_ms = round((time.perf_counter() - inicio) * 1000, 1)
    idem_key, payload = _construir_payload(data, riesgo, extractor, tiempo_ms, firm_id)

    from core.db_manager import DatabaseManager
    sp = DatabaseManager().get_service_client()
    # No hay columna idempotency_key propia en el schema real: se guarda
    # dentro de metadata (JSONB) y se filtra por el operador ->> de
    # PostgREST para chequear duplicados.
    exist = sp.table("compliance_logs").select("id").eq("metadata->>idempotency_key", idem_key).execute()
    if exist.data:
        logger.info("Ya existe un registro para este ROL/documento (%s).", pdf_path)
        return exist.data[0]["id"]

    try:
        resp = _insert_compliance_log(sp, payload)
    except RedFailSafeError as e:
        _log_error("insert_compliance_logs_fallo", e, payload)
        return None

    if resp.data:
        row_id = resp.data[0]["id"]
        logger.info("Compliance log creado: id=%s dictamen=%s tiempo_procesamiento_ms=%s", row_id, riesgo["dictamen_final"], tiempo_ms)
        return row_id

    _log_error("insert_sin_data", "Insert no devolvio datos", payload)
    return None


# --------------------------------------------------------------------------- #
# Cron: novedades de tribunal (placeholder -- reemplazar por API real)
# --------------------------------------------------------------------------- #
def consultar_tribunal(rol: str) -> dict:
    return {
        "etapa_actual": "prueba",
        "proximo_plazo": (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%d/%m/%Y"),
        "resumen": "Se ha abierto término probatorio. Se fija audiencia de prueba para dentro de 30 días.",
    }


def actualizar_o_crear_log(rol, firm_id=None):
    from core.db_manager import DatabaseManager
    sp = DatabaseManager().get_service_client()
    novedad = consultar_tribunal(rol)
    idem_key = hashlib.sha256(f"cron_{rol}_{novedad['etapa_actual']}_{novedad['proximo_plazo']}".encode()).hexdigest()

    if sp.table("compliance_logs").select("id").eq("metadata->>idempotency_key", idem_key).execute().data:
        logger.info("Novedad ya registrada para ROL %s", rol)
        return

    payload = {
        "rol": rol,
        "etapa_procesal": novedad["etapa_actual"],
        "riesgo_detectado": novedad["resumen"],
        "dictamen": "PENDIENTE",
        "metadata": {
            "proximo_plazo": novedad["proximo_plazo"],
            "idempotency_key": idem_key,
            "firm_id": firm_id,
            "origen": "cron",
        },
    }
    try:
        _insert_compliance_log(sp, payload)
        logger.info("Actualización registrada para ROL %s", rol)
    except RedFailSafeError as e:
        _log_error("cron_insert_fallo", e, payload)


def ejecutar_cron(firm_id=None):
    from core.db_manager import DatabaseManager
    sp = DatabaseManager().get_service_client()
    resp = sp.table("compliance_logs").select("rol").not_.in_("dictamen", ["APROBADO", "RECHAZADO"]).execute()
    roles = {row["rol"] for row in resp.data if row.get("rol")}
    logger.info("Procesando %d ROLes activos...", len(roles))
    for rol in roles:
        actualizar_o_crear_log(rol, firm_id)


# --------------------------------------------------------------------------- #
# Batch: procesar UNA VEZ los PDFs pendientes de una carpeta (sin loops)
# --------------------------------------------------------------------------- #
def procesar_carpeta_batch(carpeta_entrada, firm_id=None):
    """Procesa lo pendiente en carpeta_entrada UNA sola vez y termina --
    nada de loops infinitos. Para procesamiento periodico, un scheduler
    externo (cron de Railway, cron del SO) debe invocar este proceso
    repetidamente. Cada PDF se mueve a procesados/ o error/ solo despues
    de que el resultado (exito o error) ya quedo escrito en Supabase o en
    el fallback local -- un crash a mitad de proceso deja el PDF donde
    estaba para el proximo batch."""
    entrada = Path(carpeta_entrada)
    procesados = entrada / "procesados"
    con_error = entrada / "error"
    entrada.mkdir(parents=True, exist_ok=True)
    procesados.mkdir(exist_ok=True)
    con_error.mkdir(exist_ok=True)

    resultados = {"ok": [], "error": []}
    pendientes = sorted(entrada.glob("*.pdf"))
    logger.info("Batch: %d PDF(s) pendientes en %s.", len(pendientes), entrada)

    for pdf_path in pendientes:
        logger.info("Procesando %s", pdf_path.name)
        try:
            row_id = save_parsed_to_compliance(str(pdf_path), firm_id)
        except Exception as e:
            logger.exception("Fallo inesperado procesando %s", pdf_path)
            _log_error("batch_excepcion_no_manejada", e, {"archivo": pdf_path.name})
            row_id = None

        if row_id is not None:
            resultados["ok"].append(pdf_path.name)
            pdf_path.rename(procesados / pdf_path.name)
        else:
            resultados["error"].append(pdf_path.name)
            pdf_path.rename(con_error / pdf_path.name)

    logger.info("Batch finalizado: %d ok, %d con error.", len(resultados["ok"]), len(resultados["error"]))
    return resultados


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description="Herramienta Procurador")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Parsear PDF judicial y guardar en compliance_logs")
    p_parse.add_argument("pdf", help="Archivo PDF a procesar")
    p_parse.add_argument("--firm-id", default=os.getenv("MIGRATION_FIRM_ID"))
    p_parse.add_argument("--dry-run", action="store_true",
                          help="Solo extraer y evaluar riesgo; no escribe en compliance_logs ni requiere credenciales de Supabase")

    p_cron = sub.add_parser("cron", help="Ejecutar actualización de todos los ROLes activos")
    p_cron.add_argument("--firm-id", default=os.getenv("MIGRATION_FIRM_ID"))

    p_batch = sub.add_parser("batch", help="Procesar una vez los PDFs pendientes en una carpeta y salir")
    p_batch.add_argument("carpeta", help="Carpeta con PDFs pendientes")
    p_batch.add_argument("--firm-id", default=os.getenv("MIGRATION_FIRM_ID"))

    args = parser.parse_args()
    if args.command == "parse":
        if args.dry_run:
            dry_run_parse(args.pdf)
        else:
            save_parsed_to_compliance(args.pdf, args.firm_id)
    elif args.command == "cron":
        ejecutar_cron(args.firm_id)
    elif args.command == "batch":
        procesar_carpeta_batch(args.carpeta, args.firm_id)


if __name__ == "__main__":
    main()
