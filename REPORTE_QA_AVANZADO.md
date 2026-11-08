# Reporte de QA Avanzado — DepaFix (API FastAPI + CEO Mente 360)

Fecha: 3 de noviembre de 2026.
Sistema audito: `api_cotizador.py` (FastAPI) y modificacion de `mente_360.py` (CEO Cotizador).
Intérprete de pruebas: `python3` (sistema, con `fastapi==0.138.2`, `uvicorn==0.49.0`, `python-multipart==0.0.33`).
Contexto previo: `REPORTE_QA.md` (QA del ciclo Flask + `procesar_subcontrato.py`).

---

## Resumen ejecutivo

| Componente | Estado QA | Veredicto |
|---|---|---|
| **API REST** (`api_cotizador.py` — `POST /cotizar`) | ✅ **FUNCIONA** | `/health` → 200 OK. `POST /cotizar` con PDF real → **200 OK**, genera HTML y devuelve totales coherentes (neto, IVA y total cliente). Validaciones de seguridad/lógica implementadas y verificadas. |
| **CEO Cotizador** (`mente_360.py` — pedido de presupuesto) | ✅ **FUNCIONA** | Detección de palabras clave ✅. Ejecución de `procesar_subcontrato.py` ✅. Fallback de resolución de PDF restaurado ✅. |

---

## 1. API REST — `api_cotizador.py`

### Checklist de pruebas ejecutadas

| # | Prueba | Resultado |
|---|---|---|
| 1 | `python3 -m py_compile api_cotizador.py` | ✅ OK |
| 2 | `GET /health` | ✅ 200 `{"status":"ok"}` |
| 3 | `POST /cotizar` con PDF válido (`cotizacion.pdf`, proyecto `PRY-BLANCO-1313`) | ✅ 200 → `{"success":true,"total_cliente":3148740,"total_iva":502740,...}` |
| 4 | `POST /cotizar` con `proyecto=../../evil` | ✅ **400** `{"detail":"Codigo de proyecto invalido"}` |
| 5 | `POST /cotizar` con `fecha_requerida=2026-13-45` | ✅ **400** `{"detail":"Fecha requerida invalida (formato YYYY-MM-DD)"}` |
| 6 | `POST /cotizar` con archivo `.txt` | ✅ **400** `{"detail":"Solo se permiten archivos PDF"}` |
| 7 | `GET /api/materiales/{proyecto}` | ✅ 200 con datos de Supabase (`proyecto_materiales`) |

### Totales validados en el último run (`procesar_subcontrato.py` con margen 0.35)

- Costo real proveedor: `$1.960.000`
- Venta neta (+35%): `$2.646.000`
- IVA (19%): `$502.740`
- **Total cliente: `$3.148.740`**

Consistencia comprobada: `total_cliente = neto + IVA` ✅ y `IVA = neto × 0.19` ✅.

### Errores encontrados y como se solucionaron

| # | Error | Severidad | Estado |
|---|---|---|---|
| 1 | **Path traversal**: `proyecto` se concatenaba sin sanitizar (`presupuesto_{proyecto}.html`) → riesgo de path traversal. | Alta (seguridad) | ✅ **RESUELTO**: se implementó `validar_proyecto()` (solo alfanumérico, `-`, `_`). Prueba con `../../evil` → 400. |
| 2 | **Falta de validación de `fecha_requerida`**: se aceptaban strings arbitrarios. | Media (lógica) | ✅ **RESUELTO**: `datetime.strptime(fecha_requerida, "%Y-%m-%d")`. Prueba con `2026-13-45` → 400. |
| 3 | **Nombre de archivo subido sin `secure_filename`**: `uuid + filename` original → riesgo path traversal. | Media (seguridad) | ✅ **RESUELTO**: `secure_filename(pdf.filename)`. |
| 4 | **`File(..., max_length=16MB)` incompatible** con `fastapi==0.138.2` + pydantic v2 → `TypeError: Unable to apply constraint 'max_length'` → **500 en todos los `/cotizar`**. | Alta (funcional) | ✅ **RESUELTO**: constraint removido; validación de extensión se mantiene en handler. (Límite de 16MB queda como pendiente de middleware). |
| 5 | **Dependencia faltante**: `requirements.txt` no listaba `fastapi`, `uvicorn`, `python-multipart` → la API no podía instalarse/ejecutarse desde requirements. | Alta (infra) | ✅ **RESUELTO**: se añadieron `fastapi==0.138.2`, `uvicorn==0.49.0`, `python-multipart==0.0.33`. |
| 6 | **Intérprete del subprocess**: se usaba `"python3"` fijo para `procesar_subcontrato.py`. | Baja (infra) | ✅ **RESUELTO**: se usa `sys.executable`. |

---

## 2. CEO Cotizador — `mente_360.py`

### Pruebas de detección y ejecucion

| Prueba | Resultado |
|---|---|
| `es_pedido_presupuesto("presupuesto ceramica")` | ✅ True |
| `es_pedido_presupuesto("cotizar la obra")` | ✅ True |
| `es_pedido_presupuesto("me pasaron una cotizacion de 1200000")` | ✅ True |
| `es_pedido_presupuesto("hola mundo")` | ✅ False |
| `_resolver_pdf_cotizador("necesito un presupuesto para demol")` | ✅ Resuelve fallback a `/home/ibar/DepaFix_Maestro/uploads/COT-046 LINEA MAESTRA zl.pdf` |
| `_resolver_pdf_cotizador("/home/.../cotizacion.pdf necesito presupuesto")` | ✅ Resuelve la ruta indicada |
| `ejecutar_cotizador` → subprocess → `procesar_subcontrato.py` | ✅ Exit 0, HTML generado, Supabase insert OK, margen aplicado |

### Errores encontrados y como se solucionaron

| # | Error | Severidad | Estado |
|---|---|---|---|
| 1 | **Fallback de resolución de PDF ausente** en `_resolver_pdf_cotizador`: sin ruta en pregunta/args, devolvía `None` → CEO respondía "No encontré un PDF de cotización". | Media (funcional) | ✅ **RESUELTO**: se restauró fallback a PDFs por defecto del proyecto. Prueba post-fix ✅. |

### Observación de consistencia

- ⚠️ **Margen**: prompt del CEO indica margen estándar **35%**; `procesar_subcontrato.py` tenía `MARGEN_PCT = 0.40`; `REPORTE_QA.md` documentaba 0.35. **Solución aplicada**: `MARGEN_PCT = 0.35` en `procesar_subcontrato.py` (alineación con decisión previa de QA). Último run de cotización con margen 0.35 → total cliente `$3.148.740` ✅.

---

## 3. Resumen de estado final

| Ítem | Estado |
|---|---|
| **API REST** (`/health`, `POST /cotizar`, `GET /api/materiales`) | ✅ **FUNCIONA** |
| **CEO Cotizador** (detección + ejecución + fallback) | ✅ **FUNCIONA** |
| **Errores resueltos** | 7 (1 funcional crítico de max_length, 2 de seguridad, 2 de validación, 1 de dependencia, 1 de margen/fallback) |
| **Pendientes menores** | Implementar límite de tamaño de upload (16MB) vía middleware si se requiere; re-ejecutar QA completo del CEO (LLM) cuando corresponda. |

---

## 4. Comandos exactos para probar (copiar / ejecutar)

### A. Compilación de los tres frentes

```bash
cd /home/ibar/DepaFix_Maestro
python3 -m py_compile api_cotizador.py mente_360.py procesar_subcontrato.py app.py && echo PY_COMPILE_OK
```

### B. Pruebas de la API REST (FastAPI)

```bash
# Levantar servidor (puerto 8010 para no pisar el de producción en :8000)
python3 -m uvicorn api_cotizador:app --host 127.0.0.1 --port 8010

# Salud
curl -s -w "\nHTTP_CODE:%{http_code}\n" http://127.0.0.1:8010/health

# Cotizacion con PDF real
curl -s -X POST http://127.0.0.1:8010/cotizar \
  -F "pdf=@/home/ibar/DepaFix_Maestro/cotizacion.pdf;type=application/pdf" \
  -F "proyecto=PRY-BLANCO-1313" \
  -F "proveedor=TEST" -F "sku_prefix=TEST" -F "fecha_requerida=2026-11-10" \
  -w "\nHTTP_CODE:%{http_code}\n"

# Seguridad: proyecto con path traversal (esperado: 400)
curl -s -X POST http://127.0.0.1:8010/cotizar \
  -F "pdf=@/home/ibar/DepaFix_Maestro/cotizacion.pdf;type=application/pdf" \
  -F "proyecto=..%2F..%2Fevil" -F "proveedor=TEST" -F "sku_prefix=TEST" -F "fecha_requerida=2026-11-10" \
  -w "\nHTTP_CODE:%{http_code}\n"

# Validacion: fecha invalida (esperado: 400)
curl -s -X POST http://127.0.0.1:8010/cotizar \
  -F "pdf=@/home/ibar/DepaFix_Maestro/cotizacion.pdf;type=application/pdf" \
  -F "proyecto=PRY-BLANCO-1313" -F "proveedor=TEST" -F "sku_prefix=TEST" -F "fecha_requerida=2026-13-45" \
  -w "\nHTTP_CODE:%{http_code}\n"

# Materiales por proyecto
curl -s -w "\nHTTP_CODE:%{http_code}\n" http://127.0.0.1:8010/api/materiales/PRY-QAMA-2026
```

### C. Pruebas del CEO (Mente 360) — logica de cotizador

```bash
cd /home/ibar/DepaFix_Maestro

# Deteccion de palabras clave
.venv/bin/python -c "import mente_360 as m; print(m.es_pedido_presupuesto('presupuesto ceramica')); print(m._resolver_pdf_cotizador('necesito un presupuesto para demol'))"

# Ejecucion end-to-end del cotizador desde el CEO
.venv/bin/python mente_360.py "presupuesto para demol, usar /home/ibar/DepaFix_Maestro/cotizacion.pdf"
```

### D. Prueba directa del motor de cotizacion (script)

```bash
cd /home/ibar/DepaFix_Maestro
python3 procesar_subcontrato.py \
  --archivo /home/ibar/DepaFix_Maestro/cotizacion.pdf \
  --proyecto "QA-EXT-2026" \
  --proveedor "AMDQA" \
  --sku-prefix "AMDQA" \
  --fecha-requerida "2026-11-10"
```

---

## 5. Conclusión

- **API REST: ✅ FUNCIONA** — con los fixes aplicados (validacion de proyecto, fecha, secure_filename, parseo de totales, dependencias, subprocess). Se validaron health, cotizar y materiales.
- **CEO Cotizador: ✅ FUNCIONA** — con deteccion de keywords, ejecucion del script y fallback de PDF restaurados; margen alineado a 35%.
