# Reporte de QA — CEO, subcontrato y Supabase

Fecha: 2 de noviembre de 2026.
Entorno: `/home/ibar/DepaFix_Maestro`, intérprete `.venv/bin/python`.

## Resumen

| Componente | Estado | Evidencia |
|---|---|---|
| CEO — consulta de cerámica | ⚠️ Responde sin crash, pero sin rango | No hay cotizaciones de cerámica en `coach_tierra`; el CEO no inventa y pide cotización específica. |
| CEO — cotización + margen | ✅ | Calcula margen 35%: `$1.200.000 -> $1.620.000`. |
| PDF de subcontrato | ✅ | 6 partidas, costo real `$268.660`, cliente `$362.691`, margen 35%. PDF en `/home/ibar/chrome_sockets/opencode/presupuesto_QA_AMD.pdf`. |
| Inserción en Supabase | ❌ | `proyecto_materiales` no existe: `PGRST205`. No se insertó nada. |
| RPC `match_coach_tierra` | ⚠️ | Tiene `p_tipo`, pero `p_tipo='cotizacion'` devuelve 0 filas. El fallback por tabla directa sí funciona. |
| `docker-compose.yml` | ⚠️ | `docker compose config -q` OK. No se ejecutó `up` (indicación del usuario). |

## 1. CEO

### Consulta 1
Comando:
```bash
.venv/bin/python mente_360.py "presupuesto cerámica 50m2 Macul"
```

Log: `/home/ibar/chrome_sockets/opencode/ceo_q1_final3.txt`

Ruta: Tierra → Profesor Tierra → Coach Presupuestos. Filtro `tipo='cotizacion'`: 88 filas evaluadas, 6 fragmentos. Las 88 cotizaciones **no contienen la palabra “cerámica” ni “porcelanato”**. Respuesta exacta:

```text
Estamos respondiendo desde el equipo de "Mente 360" de DepaFix, con la supervisión del Profesor Supervisor — Elemento Tierra y el apoyo del Coach Presupuestos (Elemento Tierra).

Lamentablemente, en el contexto recuperado no se encuentra información específica sobre el precio de cerámica por metro cuadrado. Sin embargo, puedo ofrecerte un presupuesto referencial basado en partidas similares.

Si consideramos el costo de revestimientos de muros y tabiques, que es un tipo de trabajo relacionado, no se especifica un precio unitario exacto para cerámica. Por lo tanto, no puedo proporcionarte un precio directo para los 50 m² que solicitas.

Te recomendaría solicitar una cotización específica para cerámica a un proveedor local o a través de nuestra plataforma para obtener un precio exacto y actualizado. Si necesitas más información o asistencia, no dudes en preguntar.
```

Conclusión: no es un fallo de prompt; es ausencia de datos de cerámica. Para probar un presupuesto con cifras hay que cargar una cotización de cerámica o usar una partida existente con unidad m² y precio unitario explícito.

### Consulta 2
Comando:
```bash
.venv/bin/python mente_360.py "me pasaron una cotización de 1.200.000, agrégale margen"
```

Log: `/home/ibar/chrome_sockets/opencode/ceo_q2_final2.txt`

Ruta: Metal → Profesor Metal → Coach Finanzas. Respuesta exacta:

```text
Responden: **Profesor Supervisor — Elemento Metal** y **Coach Finanzas (Elemento Metal)** del equipo Mente 360 de DepaFix.

Cálculo con el **margen estándar DepaFix: 35%** sobre la cotización base:

- Cotización recibida: **$1.200.000 CLP**
- Margen: **35%**
- Cálculo: **$1.200.000 × 1,35 = $1.620.000 CLP**

**Resultado referencial: $1.620.000 CLP** por el servicio/obra cotizado, sin IVA u otros impuestos o alcances adicionales.

Si el margen debe aplicarse como porcentaje sobre el precio final, el cálculo cambia; confírmamelo y lo ajusto.
```

Observación: el router clasificó “cotización + margen” como Metal/Finanzas, no como Tierra/Presupuestos. La respuesta es numéricamente correcta.

## 2. PDF de subcontrato

Comando ejecutado:
```bash
.venv/bin/python procesar_subcontrato.py \
  --pdf "/home/ibar/ARCHIVO/PPTOS/Ñuñoa/Presupuesto AMD Mantenciones - Fullprop.pdf" \
  --proyecto "QA-AMD-2026" \
  --proveedor "AMD" \
  --sku-prefix "AMDQA" \
  --cliente "Cliente QA" \
  --salida "/home/ibar/chrome_sockets/opencode/presupuesto_QA_AMD.pdf"
```

Log: `/home/ibar/chrome_sockets/opencode/procesar_amd.txt`

Salida:
```text
PDF generado: /home/ibar/chrome_sockets/opencode/presupuesto_QA_AMD.pdf
Partidas detectadas: 6
Total costo real    : $268,660
Margen aplicado     : 35%
Total cliente       : $362,691
Error insertando en Supabase: {'message': "Could not find the table 'public.proyecto_materiales' in the schema cache", 'code': 'PGRST205', 'hint': "Perhaps you meant the table 'public.decreto_materiales'", 'details': None}
```

El PDF existe, tiene 4 páginas y total `$362.691`. Incluye la cláusula legal de reajuste. Problema visual menor: las columnas **Código** y **Concepto** se superponen (`AMDQAP-i0n0t1ura de cielos`); el contenido y los totales son correctos.

`MARGEN_PCT` estaba en `0.40` y se dejó en `0.35` para alinearlo con `GUIA_PRODUCCION.md` y con el CEO.

## 3. Supabase

### Inserción de materiales
No se insertó nada. La tabla `proyecto_materiales` no existe. `decreto_materiales` sí existe, pero **no es compatible**: sus columnas son `id`, `decreto_id`, `nombre_material`, `codigo_unidad`, `descripcion`, `line_item_id`, `created_at`.

DDL sugerido (no ejecutado; requiere acceso DDL que el `.env` actual no tiene):
```sql
create table public.proyecto_materiales (
  id bigint generated by default as identity primary key,
  proyecto_codigo text not null,
  material_sku text not null,
  descripcion text not null,
  proveedor text,
  unidad text default 'un',
  cantidad_aprobada numeric not null default 0,
  cantidad_comprada numeric not null default 0,
  precio_unitario_real_clp numeric not null default 0,
  margen_aplicado_pct numeric not null default 35,
  precio_unitario_cliente_clp numeric not null default 0,
  estado_compra text not null default 'pendiente',
  fecha_requerida date,
  notas text,
  created_at timestamptz not null default now(),
  unique (proyecto_codigo, material_sku, descripcion)
);
```

### RPC `match_coach_tierra`
Firma actual expuesta por PostgREST: `query_embedding` (requerido), `match_count`, `p_tipo`. No tiene `match_threshold`.

Pruebas:
- `p_tipo='cotizacion'` → 0 filas.
- Sin `p_tipo` → 5 filas, pero con `metadata.tipo = null`.
- Tabla directa `.eq("metadata->>tipo","cotizacion")` → 88 filas.
- `validar_ingesta.py` envía `match_threshold`; la RPC actual no lo acepta y cae al fallback directo. Aun así devuelve 5 resultados (`0.8629`, `0.8577`, `0.8525`, `0.8525`, `0.8517`).

Causa probable: la función filtra por una columna `tipo` en vez de `metadata->>'tipo'`. Corregir el `WHERE` a `metadata->>'tipo' = p_tipo` y alinear la firma con los scripts (agregar `match_threshold` o quitarlo de los scripts).

## 4. Archivos relevantes

- `mente_360.py`: restaurado a la versión larga, con argumento por CLI y reglas de presupuesto/margen.
- `procesar_subcontrato.py`: margen 35%, PDF y upsert a `proyecto_materiales`.
- `docker-compose.yml`: config válida; no ejecutado.
- `validar_ingesta.py`: validación con fallback directo; RPC desalineada.
- Logs: `ceo_q1_final3.txt`, `ceo_q2_final2.txt`, `procesar_amd.txt`, `val_final.txt` en `/home/ibar/chrome_sockets/opencode/`.

## 5. Pendientes antes de producción

1. Crear `proyecto_materiales` con el DDL anterior.
2. Corregir el filtro `p_tipo` del RPC y decidir si se mantiene `match_threshold`.
3. Cargar una cotización real de cerámica si se quiere probar ese caso con cifras.
4. Revisar el layout del PDF (columnas Código/Concepto) y la cláusula legal incluida.
5. Confirmar el margen definitivo: 35% (documentación) vs 40% (valor que tenía el script).
6. Ejecutar `docker compose up` cuando el usuario lo autorice.
