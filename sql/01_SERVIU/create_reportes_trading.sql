-- reportes_trading: reportes periodicos (horario/diario/semanal/quincenal/
-- mensual) generados por src/trading/report_generator.py a partir de
-- operaciones_ejecutadas (señales COMPRA/VENTA reales) y salud_agentes
-- (activos_analizados/señales_detectadas por ciclo, usado para estimar
-- ESPERA -- ver docstring de report_generator.py).

CREATE TABLE IF NOT EXISTS reportes_trading (
    id SERIAL PRIMARY KEY,
    tipo TEXT NOT NULL,  -- 'horario', 'diario', 'semanal', 'quincenal', 'mensual'
    periodo TEXT NOT NULL,  -- timestamp ISO de cierre de la ventana del reporte
    resumen JSONB,
    detalle JSONB,
    tendencias JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- report_generator.py consulta "cual fue el ultimo reporte de este tipo"
-- en cada ciclo (~cada 5 min, ver trading_orchestrator.py) para decidir si
-- ya vencio la ventana -- este indice es lo que hace esa consulta liviana.
CREATE INDEX IF NOT EXISTS idx_reportes_trading_tipo_fecha
    ON reportes_trading (tipo, created_at DESC);

COMMENT ON TABLE reportes_trading IS
    'Reportes periodicos de trading generados por src/trading/report_generator.py. tipo+created_at define la cadencia; no hay scheduler separado, se generan oportunistamente en cada ciclo de trading_orchestrator.py cuando la ventana del tipo ya vencio.';

-- Mismo patron de seguridad que operaciones_ejecutadas/alertas_precio_serviu/
-- salud_agentes: RLS activado sin policy para anon a proposito. Se escribe
-- y se lee con SUPABASE_SERVICE_ROLE_KEY (bypassea RLS).
ALTER TABLE reportes_trading ENABLE ROW LEVEL SECURITY;
