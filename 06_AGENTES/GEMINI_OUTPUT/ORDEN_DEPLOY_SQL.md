# Orden de aplicación de los 5 scripts maestros

Los 6 archivos de `sql/` quedaron consolidados en 5 masters idempotentes
(`CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE`, `ADD COLUMN IF NOT EXISTS`),
generados desde el esquema real de Supabase. En una base ya poblada se pueden
re-ejecutar sin riesgo; en un despliegue desde cero, el orden importa por las
dependencias (FK, roles) entre dominios.

## Orden

1. **`02_PROCURADOR/sql/02_procurador_master.sql`**
   Crea `clientes`, del cual dependen `presupuestos.cliente_id` (dominio
   SERVIU) y `tokens.usuario_id`.

2. **`01_SERVIU/sql/01_serviu_master.sql`**
   Requiere `clientes` (paso 1). También crea el rol `bi_readonly`
   (`CREATE ROLE ... LOGIN`), referenciado por policies en los masters de
   PROCURADOR y TRADE_CRIPTO — por eso va antes que esos dos.
   Incluye el ledger `records`/`audit_chain`/`user_keys` del que depende
   `line_items`.

3. **`03_TRADE_CRIPTO/sql/03_trade_core.sql`**
   Independiente de SERVIU/PROCURADOR en cuanto a FKs, pero sus policies
   `TO bi_readonly` requieren que el rol ya exista (paso 2).

4. **`03_TRADE_CRIPTO/sql/03_trade_analytics.sql`**
   Requiere `03_trade_core.sql` (paso 3): la vista `vista_reporte_bi`
   hace `SELECT ... FROM operaciones_ejecutadas`.

5. **`04_MERCADO_PUBLICO/sql/04_mercado_publico_master.sql`**
   Sin dependencias cruzadas. Hoy solo contiene `scrapers_logs` — no
   existe aún tabla de catálogo/licitaciones de Mercado Público en
   Supabase (el scraping es enriquecimiento posterior, ver memoria de
   proyecto).

6. **`06_AGENTES/sql/06_agentes_master.sql`**
   Sin dependencias cruzadas con los otros dominios (`metricas_diarias`
   depende de `campanas_meta`, pero ambas están en este mismo archivo).

## Notas

- **IMPORTANTE — `bi_readonly` con password placeholder**: el `CREATE ROLE`
  en `01_serviu_master.sql` usa `PASSWORD 'CAMBIAR_ESTA_PASSWORD_ANTES_DE_USAR'`
  (heredado de `sql/create_bi_readonly.sql`, ya eliminado). En cualquier
  entorno nuevo, cambiar esa contraseña antes de exponer el rol.
- **Contradicción de seguridad sin resolver** (heredada, no introducida por
  esta consolidación): en `presupuestos`, la policy `Permitir_Lectura_Total`
  usa `USING (true)` sin `TO`, o sea aplica a `PUBLIC` (incluido `anon`) — el
  `REVOKE ALL ... FROM anon` del mismo archivo no la neutraliza. Sigue así
  porque decidir si `presupuestos` debe ser público es una decisión de
  producto, no algo que resolver al consolidar scripts.
- La vista `v_analisis_desviacion` (en `01_serviu_master.sql`) referencia
  `precios_serviu.moneda`, columna que se agrega en el mismo script pero que
  ningún proceso puebla todavía — confirmar con quien migra datos de
  Mercado Público/SERVIU cómo se va a cargar.
- El submódulo `01_SERVIU_backup/` (repo git aparte) no forma parte de esta
  consolidación y no se tocó.
