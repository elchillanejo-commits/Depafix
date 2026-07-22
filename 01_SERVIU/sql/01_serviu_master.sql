-- ============================================================
-- 01_serviu_master.sql
-- Dominio SERVIU: decretos, materiales, precios, rubros contables
-- y la cadena de auditoría (records/audit_chain) de la que depende
-- line_items. Generado a partir del esquema real de Supabase
-- (pg_catalog / information_schema), no de los .sql sueltos previos.
--
-- Dependencia cruzada: presupuestos.cliente_id -> clientes(id).
-- clientes vive en 02_procurador_master.sql: aplicar ese script
-- antes que este en un despliegue desde cero.
--
-- Idempotente: seguro de re-ejecutar contra una base ya poblada.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------
-- Rol de solo lectura para Power BI (compartido con 02_PROCURADOR
-- y 03_TRADE_CRIPTO, que también referencian "TO bi_readonly" en
-- sus policies). Se crea acá porque este es el primer master de la
-- cadena de despliegue. Ver sql/create_bi_readonly.sql (origen,
-- ahora incorporado aquí) para el razonamiento de seguridad.
-- ------------------------------------------------------------
DO $do$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'bi_readonly') THEN
        CREATE ROLE bi_readonly LOGIN PASSWORD 'CAMBIAR_ESTA_PASSWORD_ANTES_DE_USAR';
    END IF;
END
$do$;
GRANT CONNECT ON DATABASE postgres TO bi_readonly;
GRANT USAGE ON SCHEMA public TO bi_readonly;

-- ------------------------------------------------------------
-- Ledger genérico de registros inmutables (usado por line_items
-- y por audit_chain para el hash-chain de integridad)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS records (
    record_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash    text NOT NULL,
    raw_payload     jsonb NOT NULL,
    idempotency_key text NOT NULL,
    created_at      timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS records_idempotency_key_key ON records(idempotency_key);

CREATE TABLE IF NOT EXISTS audit_chain (
    event_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id  uuid REFERENCES records(record_id),
    event_type text NOT NULL,
    event_hash text NOT NULL,
    created_at timestamptz DEFAULT now()
);
ALTER TABLE audit_chain ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS user_keys (
    user_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_key text NOT NULL,
    algorithm  text NOT NULL DEFAULT 'RSA',
    created_at timestamptz DEFAULT now()
);
ALTER TABLE user_keys ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION enforce_chain_hash()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
begin
  new.event_hash := encode(digest(new.record_id::text || new.event_type, 'sha256'), 'hex');
  return new;
end;
$function$;

DROP TRIGGER IF EXISTS trg_hash ON audit_chain;
CREATE TRIGGER trg_hash BEFORE INSERT ON audit_chain
    FOR EACH ROW EXECUTE FUNCTION enforce_chain_hash();

-- ------------------------------------------------------------
-- Decretos SERVIU y su contenido normativo
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decretos (
    id                 SERIAL PRIMARY KEY,
    numero             varchar(20) NOT NULL UNIQUE,
    titulo             text,
    fecha_publicacion  date,
    url                text,
    created_at         timestamptz DEFAULT now()
);
COMMENT ON COLUMN decretos.numero IS 'Número del decreto (ej: 49)';
CREATE INDEX IF NOT EXISTS idx_decretos_numero ON decretos(numero);
ALTER TABLE decretos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "bi_readonly_decretos" ON decretos;
CREATE POLICY "bi_readonly_decretos" ON decretos FOR SELECT TO bi_readonly USING (true);

CREATE TABLE IF NOT EXISTS decreto_articulos (
    id         SERIAL PRIMARY KEY,
    decreto_id integer NOT NULL REFERENCES decretos(id) ON DELETE CASCADE,
    numero     varchar(20),
    contenido  text,
    created_at timestamptz DEFAULT now()
);
COMMENT ON COLUMN decreto_articulos.decreto_id IS 'Referencia al decreto padre';
CREATE INDEX IF NOT EXISTS idx_decreto_articulos_decreto ON decreto_articulos(decreto_id);
ALTER TABLE decreto_articulos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "bi_readonly_decreto_articulos" ON decreto_articulos;
CREATE POLICY "bi_readonly_decreto_articulos" ON decreto_articulos FOR SELECT TO bi_readonly USING (true);

CREATE TABLE IF NOT EXISTS decreto_materiales (
    id              SERIAL PRIMARY KEY,
    decreto_id      integer NOT NULL REFERENCES decretos(id) ON DELETE CASCADE,
    nombre_material text NOT NULL,
    codigo_unidad   varchar(20),
    descripcion     text,
    line_item_id    integer,
    created_at      timestamptz DEFAULT now()
);
COMMENT ON COLUMN decreto_materiales.line_item_id IS 'ID de line_items (referencia manual, sin FK)';
CREATE INDEX IF NOT EXISTS idx_decreto_materiales_decreto ON decreto_materiales(decreto_id);
CREATE INDEX IF NOT EXISTS idx_decreto_materiales_nombre ON decreto_materiales(nombre_material);
ALTER TABLE decreto_materiales ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "bi_readonly_decreto_materiales" ON decreto_materiales;
CREATE POLICY "bi_readonly_decreto_materiales" ON decreto_materiales FOR SELECT TO bi_readonly USING (true);

CREATE TABLE IF NOT EXISTS line_items (
    line_item_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id       uuid REFERENCES records(record_id) ON DELETE CASCADE,
    cantidad        numeric NOT NULL,
    material        text NOT NULL,
    precio_unitario numeric NOT NULL,
    rubro           text,
    created_at      timestamptz DEFAULT now()
);
ALTER TABLE line_items ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------
-- Precios SERVIU y reglas de clasificación por rubro
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS precios_serviu (
    id              SERIAL PRIMARY KEY,
    item            text NOT NULL,
    unidad          text,
    valor_unitario  numeric NOT NULL,
    fuente          text,
    idempotency_key text NOT NULL UNIQUE,
    created_at      timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_precios_serviu_item ON precios_serviu(item);
ALTER TABLE precios_serviu ENABLE ROW LEVEL SECURITY;

-- Clasificación de rubro y trazabilidad de calidad de dato (antes
-- sql/migrate_precios_serviu_rubro.sql). precios_serviu nunca tuvo
-- columna `rubro` en producción; se agrega acá junto con el resto
-- del esquema para que un despliegue nuevo la tenga desde el día 1.
ALTER TABLE precios_serviu
    ADD COLUMN IF NOT EXISTS rubro TEXT,
    ADD COLUMN IF NOT EXISTS estado_dato TEXT NOT NULL DEFAULT 'OK';
CREATE INDEX IF NOT EXISTS idx_precios_serviu_rubro ON precios_serviu(rubro);
CREATE INDEX IF NOT EXISTS idx_precios_serviu_estado_dato ON precios_serviu(estado_dato);
COMMENT ON COLUMN precios_serviu.rubro IS 'Categoría de gasto (Construcción, Electricidad, ...). NULL hasta que auditor_precios_ia.py la clasifique.';
COMMENT ON COLUMN precios_serviu.estado_dato IS 'OK | ERROR_DATOS. ERROR_DATOS = el auditor no pudo clasificar rubro y/o falta valor_unitario; requiere revisión manual.';

-- NOTA: sql/create_view_analisis_desviacion.sql (fuente de la vista más
-- abajo) referenciaba una columna `moneda` que nunca existió en ningún
-- .sql previo del repo ni en producción -- tampoco la agrega
-- migrate_precios_serviu_rubro.sql. Se agrega acá tal cual la usaba la
-- vista original (CASE WHEN moneda = 'UF' ...), sin inventar una fuente
-- de verdad distinta para esa lógica; hay que confirmar con quien migra
-- los datos de Mercado Público/SERVIU cómo se va a poblar.
ALTER TABLE precios_serviu ADD COLUMN IF NOT EXISTS moneda TEXT;

-- Cierre de acceso de 'anon' + policy exclusiva para bi_readonly
-- (antes sql/create_bi_readonly.sql). En vivo, precios_serviu tenía
-- RLS activado pero sin policy alguna -- bi_readonly no podía leerla
-- todavía; esto lo deja funcional.
GRANT SELECT ON public.precios_serviu TO bi_readonly;
REVOKE ALL ON public.precios_serviu FROM anon;
DROP POLICY IF EXISTS "bi_readonly_select" ON precios_serviu;
CREATE POLICY "bi_readonly_select" ON precios_serviu FOR SELECT TO bi_readonly USING (true);

-- Auditoría de anomalías de precio detectadas por core/trade_agent.py
-- (antes sql/create_alertas_precio_serviu.sql). Mismo patrón que
-- operaciones_ejecutadas: hash_control = SHA-256 del item + estadísticas
-- del rubro que motivaron la alerta.
CREATE TABLE IF NOT EXISTS alertas_precio_serviu (
    id                  SERIAL PRIMARY KEY,
    item_id             INTEGER,
    item                TEXT,
    rubro               TEXT NOT NULL,
    valor_clp           NUMERIC NOT NULL,
    promedio_rubro_clp  NUMERIC NOT NULL,
    desviacion_pct      NUMERIC NOT NULL,
    z_score             NUMERIC,
    tipo                TEXT NOT NULL,
    severidad           TEXT NOT NULL,
    n_muestras_rubro    INTEGER NOT NULL,
    desde_cache         BOOLEAN DEFAULT false,
    hash_control        TEXT NOT NULL,
    detectado_at        TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alertas_precio_serviu_lookup ON alertas_precio_serviu(rubro, detectado_at DESC);
COMMENT ON TABLE alertas_precio_serviu IS 'Auditoria de anomalias de precio detectadas por core/trade_agent.py. hash_control = SHA-256 del item + estadisticas del rubro que motivaron la alerta. desde_cache=true indica que la corrida uso el snapshot local porque Supabase no respondio.';
-- RLS activado sin policy para anon a propósito: trade_agent.py escribe
-- con SUPABASE_SERVICE_ROLE_KEY (bypassea RLS).
ALTER TABLE alertas_precio_serviu ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS reglas_rubros (
    id            SERIAL PRIMARY KEY,
    palabra_clave text NOT NULL,
    rubro         text NOT NULL,
    prioridad     integer NOT NULL DEFAULT 0,
    created_at    timestamptz DEFAULT now(),
    UNIQUE (palabra_clave, rubro)
);
CREATE INDEX IF NOT EXISTS idx_reglas_rubros_prioridad ON reglas_rubros(prioridad DESC);

-- Seed inicial (antes en sql/migrate_precios_serviu_rubro.sql), tomado
-- 1:1 del dict RUBROS vigente en Aquiles/scrapers/multi_dia.py.
INSERT INTO reglas_rubros (palabra_clave, rubro, prioridad) VALUES
    ('construcción', 'Construcción', 10),
    ('construccion', 'Construcción', 10),
    ('electricidad', 'Electricidad', 10),
    ('eléctric', 'Electricidad', 10),
    ('electric', 'Electricidad', 9),
    ('fontanería', 'Fontanería', 10),
    ('fontaneria', 'Fontanería', 10),
    ('gasfitería', 'Fontanería', 9),
    ('gasfiteria', 'Fontanería', 9),
    ('gráfica', 'Gráfica', 10),
    ('grafica', 'Gráfica', 10),
    ('publicidad', 'Gráfica', 8),
    ('impresión', 'Gráfica', 8),
    ('impresion', 'Gráfica', 8),
    ('capacitación', 'Capacitación', 10),
    ('capacitacion', 'Capacitación', 10),
    ('formación', 'Capacitación', 8),
    ('formacion', 'Capacitación', 8),
    ('entrenamiento', 'Capacitación', 7)
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS reglas_rubros_exclusiones (
    id               SERIAL PRIMARY KEY,
    rubro            text NOT NULL,
    palabra_excluida text NOT NULL,
    created_at       timestamptz DEFAULT now(),
    UNIQUE (rubro, palabra_excluida)
);
COMMENT ON TABLE reglas_rubros_exclusiones IS 'Palabras que invalidan un match de reglas_rubros para ese rubro (evita falsos positivos como "construcción de barcos" -> Construcción). Consumida por core/auditor_precios_ia.py.';

-- Seed inicial (antes en sql/create_reglas_rubros_exclusiones.sql).
INSERT INTO reglas_rubros_exclusiones (rubro, palabra_excluida) VALUES
    ('Construcción', 'barco'),
    ('Construcción', 'bote'),
    ('Construcción', 'naval'),
    ('Construcción', 'pesca'),
    ('Construcción', 'pesquero'),
    ('Construcción', 'marítimo'),
    ('Construcción', 'maritimo'),
    ('Construcción', 'embarcación'),
    ('Construcción', 'embarcacion'),
    ('Construcción', 'buque')
ON CONFLICT DO NOTHING;

-- Promedio/desviación estándar de precio (en CLP) por rubro crítico,
-- para que trade_agent.py haga una sola consulta liviana en vez de
-- calcular estadísticas del lado de Python (antes
-- sql/create_view_analisis_desviacion.sql). Solo filas estado_dato='OK'
-- y rubros presentes en reglas_rubros. Conversión UF->CLP inline: los
-- registros fuente=SERVIU están en UF, los de MERCADO_PUBLICO en CLP.
CREATE OR REPLACE VIEW v_analisis_desviacion AS
SELECT
    rubro,
    COUNT(*)                                               AS n_muestras,
    ROUND(AVG(valor_clp)::numeric, 2)                      AS promedio_clp,
    ROUND(COALESCE(STDDEV_SAMP(valor_clp), 0)::numeric, 2) AS stddev_clp,
    ROUND(MIN(valor_clp)::numeric, 2)                      AS min_clp,
    ROUND(MAX(valor_clp)::numeric, 2)                      AS max_clp,
    MAX(created_at)                                        AS ultima_actualizacion
FROM (
    SELECT
        rubro,
        created_at,
        CASE WHEN moneda = 'UF' THEN valor_unitario * 38377.09 ELSE valor_unitario END AS valor_clp
    FROM precios_serviu
    WHERE estado_dato = 'OK'
      AND rubro IS NOT NULL
      AND valor_unitario IS NOT NULL
      AND rubro IN (SELECT DISTINCT rubro FROM reglas_rubros)
) sub
GROUP BY rubro;
COMMENT ON VIEW v_analisis_desviacion IS 'Promedio/stddev de precio en CLP por rubro crítico (rubros definidos en reglas_rubros), solo filas estado_dato=OK. Consumida por core/trade_agent.py.';

CREATE TABLE IF NOT EXISTS reglas_contables (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rubro_nombre             text NOT NULL,
    cuenta_contable_sugerida text NOT NULL,
    palabras_clave_json      jsonb NOT NULL DEFAULT '[]'::jsonb,
    prioridad                integer NOT NULL DEFAULT 0,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz
);
ALTER TABLE reglas_contables ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon_auth_select_reglas" ON reglas_contables;
CREATE POLICY "anon_auth_select_reglas" ON reglas_contables FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS "auth_insert_reglas" ON reglas_contables;
CREATE POLICY "auth_insert_reglas" ON reglas_contables FOR INSERT TO authenticated WITH CHECK (true);

CREATE TABLE IF NOT EXISTS auditoria_movimientos (
    movimiento_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    monto            numeric(12,2) NOT NULL,
    descripcion      text NOT NULL,
    clasificacion_ia text,
    confianza_ia     numeric(3,2),
    estado_revision  text NOT NULL DEFAULT 'PENDIENTE_REVISION'
        CHECK (estado_revision IN ('CLASIFICADO', 'PENDIENTE_REVISION', 'RECHAZADO', 'CONFIRMADO')),
    regla_usada_id   bigint REFERENCES reglas_contables(id),
    fecha_movimiento date,
    raw_csv_line     text,
    created_at       timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE auditoria_movimientos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "anon_auth_select_auditoria" ON auditoria_movimientos;
CREATE POLICY "anon_auth_select_auditoria" ON auditoria_movimientos FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS "auth_insert_auditoria" ON auditoria_movimientos;
CREATE POLICY "auth_insert_auditoria" ON auditoria_movimientos FOR INSERT TO authenticated WITH CHECK (true);

-- ------------------------------------------------------------
-- Presupuestos históricos (fuente de entrenamiento ML, ver
-- memoria de proyecto: Opción A sobre scraping)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS presupuestos (
    id                 SERIAL PRIMARY KEY,
    cliente            text,
    tarea              text,
    maestro            text,
    fecha              date,
    total              double precision,
    m2                 double precision,
    estado             text,
    descripcion        text,
    incluye_materiales boolean DEFAULT false,
    created_at         timestamptz DEFAULT now(),
    cliente_id         uuid REFERENCES clientes(id),
    nombre             text,
    monto_total        numeric(14,2) DEFAULT 0,
    codigo             text UNIQUE,
    updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pres_estado ON presupuestos(estado);
CREATE INDEX IF NOT EXISTS idx_pres_tarea ON presupuestos(tarea);
ALTER TABLE presupuestos ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Permitir_Lectura_Total" ON presupuestos;
CREATE POLICY "Permitir_Lectura_Total" ON presupuestos FOR SELECT USING (true);
DROP POLICY IF EXISTS "Permitir_Update_Total" ON presupuestos;
CREATE POLICY "Permitir_Update_Total" ON presupuestos FOR UPDATE USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "bi_readonly_access" ON presupuestos;
CREATE POLICY "bi_readonly_access" ON presupuestos FOR SELECT TO bi_readonly USING (true);
GRANT SELECT ON public.presupuestos TO bi_readonly;
-- NOTA (antes sql/create_bi_readonly.sql): el REVOKE de acá pretendía
-- cerrarle el acceso a 'anon', pero la policy "Permitir_Lectura_Total"
-- de más abajo usa USING(true) sin TO, o sea aplica a PUBLIC (incluido
-- anon) -- ese REVOKE no la neutraliza. Queda igual que en el archivo
-- original; no se resuelve la contradicción acá porque implica decidir
-- si presupuestos debe seguir siendo público o no.
REVOKE ALL ON public.presupuestos FROM anon;

CREATE TABLE IF NOT EXISTS partidas_presupuesto (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    presupuesto_id  integer NOT NULL REFERENCES presupuestos(id) ON DELETE CASCADE,
    descripcion     text NOT NULL,
    cantidad        numeric(10,2) NOT NULL DEFAULT 1,
    precio_unitario numeric(14,2) NOT NULL DEFAULT 0,
    orden           integer DEFAULT 0
);
