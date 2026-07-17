# 05_GUIA_CONEXION_POWERBI

Guía para que Aquiles conecte Power BI a las dos fuentes de datos de DepaFix.
Esta versión reemplaza una anterior que documentaba solo la fuente de
presupuestos (Supabase) -- se agregó la fuente de datos inmobiliarios sin
perder esa parte.

## Fuente 1: Datos Inmobiliarios (CSV local, histórico incremental)

### 1.1 Pipeline
```
src/agents/inmo_scrapper.py  --(append)-->  data/inmo_data.csv (bruto)
data/inmo_data.csv  --(quality_gate.py: valida + dedup + append)-->  data/inmo_data_clean.csv
```
Orquestado por `src/run_pipeline.py` (scraper -> quality_gate -> health_check).

### 1.2 Ruta del archivo
`data/inmo_data_clean.csv`, calculada en código como
`config.settings.BASE_DIR / 'data' / 'inmo_data_clean.csv'` -- nunca
hardcodeada. En esta máquina eso resuelve hoy a
`/home/ibar/Proyectos/DepaFix/data/inmo_data_clean.csv`; en Power BI hay que
apuntar a esa ruta resuelta (Power BI no entiende `BASE_DIR`), pero el
pipeline en sí es portable a cualquier checkout del repo.

### 1.3 Actualización -- YA NO SOBREESCRIBE
Corregido en esta versión: `quality_gate.py` antes regeneraba
`inmo_data_clean.csv` completo en cada corrida (perdía el histórico si el
bruto rotaba). Ahora hace **append incremental** -- cada corrida agrega
solo las filas nuevas y válidas, preservando todo el histórico para que
Aquiles pueda armar series de tiempo reales en Power BI. En Power BI:
`Get Data > Text/CSV`, con refresh normal (recarga el CSV completo en cada
actualización; no hace falta configurar "incremental refresh" de Power BI
para este volumen de datos).

### 1.4 Campos y tipos de datos (Power Query > Transform Data > Change Type)
| Campo | Tipo en Power BI | Notas |
|---|---|---|
| `titulo` | Texto (Text) | Identificador de la propiedad. Ver limitación abajo. |
| `precio` | Número decimal (Decimal Number) | **No dejar como texto** -- si Power BI lo detecta como texto, los KPI de evolución de precios fallan o concatenan en vez de sumar/promediar. |
| `fecha` | Fecha/hora (Date/Time), no solo Fecha | El pipeline guarda timestamp con microsegundos; truncar a día se hace en Power BI (columna calculada), no en el CSV. |

Limitación conocida (heredada de `src/agents/inmo_scrapper.py`): `titulo`
es el único identificador de propiedad hoy -- dos propiedades distintas con
el mismo título literal se verían como una sola serie en Power BI. Si el
scraper real llega a capturar una URL o ID de listing, ese campo debería
agregarse al CSV y usarse como clave en vez de `titulo`.

### 1.5 Duplicados
`quality_gate.py` ya descarta duplicados (misma propiedad + mismo precio +
mismo día) antes de que el archivo llegue a Power BI -- Aquiles no necesita
deduplicar de nuevo en Power Query. Si ve filas idénticas repetidas, es
señal de que está leyendo una copia vieja de `inmo_data_clean.csv` generada
antes de esta corrección.

### 1.6 KPI sugeridos
- Evolución de precios: `fecha` (eje X) vs `precio` (eje Y), segmentado por `titulo`.
- Distribución de valores: `titulo` vs `precio`.

## Fuente 2: Presupuestos (Supabase, rol `bi_readonly`)

### 2.1 Credenciales
- Host: Supabase Project URL (conexión directa a Postgres, Settings > Database).
- Rol: `bi_readonly`.
- Permisos: Solo SELECT (lectura), según las políticas RLS definidas en
  `04_POLITICAS_SEGURIDAD_RLS.md` -- ese documento es la fuente de verdad
  de qué tablas expone `bi_readonly` y bajo qué policy; esta guía no debe
  otorgar acceso a nada que 04 no autorice explícitamente.

### 2.2 Validación
- Usar script `src/analytics/bi_exporter.py` para una exportación local
  validada (tipos limpios, sin nulos en columnas requeridas) antes de
  conectar Power BI directo a Supabase.
- Antes de conectar en producción, confirmar con `tests/test_connectivity.py`
  y con `sql/create_bi_readonly.sql` que el rol `bi_readonly` ya está creado
  y aplicado en la base real -- ver `docs/00_ESTADO_PRODUCCION.md` para el
  estado actual (a la fecha de esa auditoría, todavía no estaba sincronizado).
