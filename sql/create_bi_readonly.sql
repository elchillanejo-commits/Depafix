-- create_bi_readonly.sql -- rol de solo lectura para Power BI sobre
-- "presupuestos". NO existía en el repo (auditoría 2026-07-16: "bi_readonly"
-- no aparece en supabase_schema.sql ni create_tokens_tables.sql) -- este
-- archivo es nuevo, correr en el SQL Editor de Supabase con permisos de owner.
--
-- Enfoque: un rol Postgres separado (bi_readonly), NO la key 'anon' del
-- proyecto. Power BI se conecta directo a Postgres (Settings > Database >
-- Connection string), con SU PROPIA contraseña, no con SUPABASE_KEY/
-- SUPABASE_SERVICE_ROLE_KEY de este repo -- así una fuga de la contraseña
-- de Power BI no compromete nada más, y viceversa.

-- ============================================================
-- 1. Rol de login, solo para Power BI
-- ============================================================
DO $do$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'bi_readonly') THEN
        CREATE ROLE bi_readonly LOGIN PASSWORD 'CAMBIAR_ESTA_PASSWORD_ANTES_DE_USAR';
    END IF;
END
$do$;

-- ============================================================
-- 2. DESINCRONIZACIÓN DETECTADA (auditoría 2026-07-16, verificado en vivo
--    con la key 'anon' contra Supabase real):
--
--      precios_serviu : anon PUEDE leer hoy -- docs/02_MODELO_DATOS_SERVIU.md
--                        y docs/04_POLITICAS_SEGURIDAD_RLS.md documentan
--                        "solo lectura vía bi_readonly", pero eso NO está
--                        aplicado en la base real.
--      velas_cripto    : anon PUEDE leer hoy -- contradice el propio
--                        sql/create_velas_cripto.sql, que documenta RLS
--                        activado sin policy para anon.
--      presupuestos    : anon PUEDE leer hoy (ya señalado en la sesión
--                        anterior, sin RLS aplicado todavía).
--
--    En Supabase, 'anon' es un ROL DE POSTGRES real (el que usa PostgREST
--    para la key pública) -- si tiene GRANT de SELECT heredado (p.ej. del
--    Table Editor, que por defecto no restringe), activar RLS con una
--    policy nueva NO alcanza: hay que revocarle el GRANT explícitamente.
--    Por eso cada bloque de abajo hace REVOKE + ENABLE RLS + policy.
-- ============================================================

-- ============================================================
-- 3. Permisos mínimos para bi_readonly: conectar + SELECT explícito
-- ============================================================
GRANT CONNECT ON DATABASE postgres TO bi_readonly;
GRANT USAGE ON SCHEMA public TO bi_readonly;
GRANT SELECT ON public.presupuestos TO bi_readonly;
GRANT SELECT ON public.precios_serviu TO bi_readonly;

-- Futuras columnas/tablas de este schema NO quedan expuestas automáticamente
-- a bi_readonly -- hay que repetir el GRANT SELECT explícito para cada
-- tabla nueva que Power BI necesite. Esto es a propósito: acceso mínimo
-- necesario, no "todo el schema public".

-- ============================================================
-- 4. Cerrar el acceso de 'anon' + RLS con policy exclusiva para bi_readonly
-- ============================================================
REVOKE ALL ON public.presupuestos FROM anon;
ALTER TABLE public.presupuestos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bi_readonly_select ON public.presupuestos;
CREATE POLICY bi_readonly_select
    ON public.presupuestos
    FOR SELECT
    TO bi_readonly
    USING (true);

REVOKE ALL ON public.precios_serviu FROM anon;
ALTER TABLE public.precios_serviu ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bi_readonly_select ON public.precios_serviu;
CREATE POLICY bi_readonly_select
    ON public.precios_serviu
    FOR SELECT
    TO bi_readonly
    USING (true);

-- velas_cripto: re-aplica exactamente lo que sql/create_velas_cripto.sql ya
-- documentaba (RLS sin policy para anon); solo agrega el REVOKE que faltaba.
REVOKE ALL ON public.velas_cripto FROM anon;
ALTER TABLE public.velas_cripto ENABLE ROW LEVEL SECURITY;

-- Sin policy de INSERT/UPDATE/DELETE para bi_readonly a propósito: con RLS
-- activado y solo policies de SELECT, cualquier intento de escritura queda
-- denegado por Postgres, no solo por el GRANT.
--
-- ADVERTENCIA: data_pipeline.py escribe en velas_cripto con la
-- SUPABASE_SERVICE_ROLE_KEY (bypassea RLS, no se ve afectado por esto).
-- injector.py y auditor_ia.py SÍ escriben con la key 'anon'
-- (DatabaseManager.get_client()) en analisis_trading y reglas_contables
-- respectivamente -- este script NO les revoca nada porque no está en el
-- alcance pedido (presupuestos/precios_serviu), pero si más adelante se
-- corre un REVOKE ALL FROM anon más amplio, van a dejar de poder escribir.

-- ============================================================
-- 5. Verificación manual (correr después, para confirmar)
-- ============================================================
-- SET ROLE bi_readonly;
-- SELECT * FROM public.presupuestos LIMIT 1;    -- debe funcionar
-- SELECT * FROM public.precios_serviu LIMIT 1;  -- debe funcionar
-- INSERT INTO public.presupuestos (cliente) VALUES ('x');  -- debe fallar
-- RESET ROLE;
-- SET ROLE anon;
-- SELECT * FROM public.presupuestos LIMIT 1;    -- debe fallar (RLS sin policy para anon)
-- RESET ROLE;
