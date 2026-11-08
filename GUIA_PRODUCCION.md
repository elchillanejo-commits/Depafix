# Guía de producción: presupuestos con subcontrato

Todos los comandos se ejecutan desde la raíz del repo con `.venv`.

## 1. Estado

| Componente | Estado |
|---|---|
| CEO (`mente_360.py`) | Responde. Sin llaves anidadas en el prompt. |
| `procesar_subcontrato.py` | Implementado. Sin prueba con PDF real. |
| `cotizar.py` → `generar_pdf_comercial` | Implementado. Requiere `docs/clausula_exencion_responsabilidad.md` (no existe). |
| `insertar_materiales.py` | Implementado. Falla: tabla `proyecto_materiales` no existe en Supabase. |

## 2. Procesar subcontrato y generar PDF cliente

Lee el PDF del contratista, infla cada precio unitario por `MARGEN_SUBCONTRATO_PCT` (0.35, constante en `procesar_subcontrato.py`) y genera el PDF cliente. El PDF no muestra costo ni margen. El desglose interno se imprime en consola.

```bash
.venv/bin/python procesar_subcontrato.py "/home/ibar/ARCHIVO/PPTOS/Ñuñoa/Presupuesto AMD Mantenciones - Fullprop.pdf" \
    --cliente "Cliente de prueba" \
    --proyecto "Mantención AMD Ñuñoa" \
    --texto-saldo "saldo contra entrega final" \
    --salida /tmp/cliente_amd.pdf
```

`--texto-saldo` es obligatorio. La condición de pago del saldo debe definirla negocio; el valor del ejemplo no está aprobado.

## 3. Verificar el PDF

```bash
.venv/bin/python -c "import pdfplumber,sys; t=''.join(p.extract_text() or '' for p in pdfplumber.open(sys.argv[1]).pages); print('exencion:', 'Exención' in t); print('validez:', 'Validez de la oferta' in t); print('comision visible:', 'Comisi' in t)" /tmp/cliente_amd.pdf
```

Resultado esperado: `exencion: True`, `validez: True`, `comision visible: False`. Si `exencion` es `False`, el PDF no tiene la cláusula, y eso indica que el archivo de cláusula no se cargó.

## 4. Consultar materiales en Supabase

Antes de insertar, revisar sin escribir:

```bash
.venv/bin/python insertar_materiales.py --pdf "/home/ibar/ARCHIVO/PPTOS/Ñuñoa/Presupuesto AMD Mantenciones - Fullprop.pdf" \
    --proyecto "PRY-VERBENAS-8925" --proveedor "AMD MANTENCIONES" --sku-prefix AMD --dry-run
```

Inserción real (solo después de crear la tabla):

```bash
.venv/bin/python insertar_materiales.py --pdf "/home/ibar/ARCHIVO/PPTOS/Ñuñoa/Presupuesto AMD Mantenciones - Fullprop.pdf" \
    --proyecto "PRY-VERBENAS-8925" --proveedor "AMD MANTENCIONES" --sku-prefix AMD
```

Consulta de lo insertado:

```bash
.venv/bin/python -c "import os; from dotenv import load_dotenv; from supabase import create_client; load_dotenv(dotenv_path='.env'); c=create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY']); [print(r) for r in c.table('proyecto_materiales').select('material_sku,descripcion,cantidad_aprobada,precio_unitario_real_clp,estado_compra').eq('proyecto_codigo','PRY-VERBENAS-8925').execute().data]"
```

Hoy el comando de consulta devuelve `PGRST205` (tabla no encontrada). Crear la tabla primero.

## 5. CEO para preguntas generales

```bash
.venv/bin/python mente_360.py "presupuesto cerámica 50m2 Macul"
.venv/bin/python mente_360.py "¿qué es un tablero eléctrico?"
```

El CEO no calcula precios ni márgenes. Para presupuestos responde que el cálculo lo hace `procesar_subcontrato.py`.

## 6. Pendientes bloqueantes

1. **Cláusula de exención:** crear `docs/clausula_exencion_responsabilidad.md` con el texto aprobado por el Procurador. No se incluye texto inventado. Sin el archivo, `generar_pdf_comercial` lanza `FileNotFoundError`.
2. **Conflicto de validez:** `docs/clausula_validez_blindada.md` dice 30 días corridos y el pie del PDF dice 15. Definir uno solo antes de enviar a clientes.
3. **Anticipo 50 %:** no hay fuente en el repo para esa condición. Confirmar con negocio. Está como parámetro `anticipo_pct=50`.
4. **Tabla `proyecto_materiales`:** no existe en Supabase. Falta el DDL y la decisión de esquema.
5. **Prueba con PDF real:** `procesar_subcontrato.py` no se ha probado con una cotización de contratista. Validar el mapeo de columnas antes de usarlo con clientes.
6. **Router (`mente_360.py`, `enrutar_pregunta`):** revisar que la plantilla no declare variables que `invoke` no recibe.
7. **Dependencias:** `pdfplumber` está en `.venv` pero no en `requirements.txt`.
8. **Arranque en Docker:** `mente_360.py` sin TTY reinicia en bucle. Falta el modo servicio en el bloque `__main__`.
