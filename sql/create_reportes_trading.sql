-- reportes_trading: reportes periodicos (quincenal/mensual) generados por
-- src/trading/analisis_periodico.py a partir de operaciones_ejecutadas
-- (senales reales COMPRA/VENTA/ESPERA) y memoria_trading (patrones
-- recalculados). No existia ninguna version de esta tabla en DepaFix --
-- la del repo hermano 01_SERVIU/05_TRADE_CRIPTO fue escrita contra un
-- esquema de operaciones_ejecutadas distinto al real (side/symbol/price),
-- asi que esta version se escribe desde cero contra el esquema vivo.

CREATE TABLE IF NOT EXISTS reportes_trading (
    id SERIAL PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('quincenal', 'mensual')),
    periodo TEXT NOT NULL,        -- timestamp ISO de cierre de la ventana del reporte
    resumen JSONB,                -- conteos por activo/senal, % alta calidad, tasas, precio promedio
    detalle JSONB,                -- patrones horarios/dia de semana, recomendaciones
    tendencias JSONB,             -- eficacia medida por herramienta (Fibonacci/FVG/Order Block/EMA50/RSI/fractalidad)
    comparativa JSONB,            -- solo 'mensual': comparacion contra el periodo anterior
    resumen_texto TEXT,           -- resumen ejecutivo en texto plano ya renderizado
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reportes_trading_tipo_fecha
    ON reportes_trading (tipo, created_at DESC);

ALTER TABLE reportes_trading ENABLE ROW LEVEL SECURITY;

-- Mismo patron que operaciones_ejecutadas/velas_cripto: RLS activado sin
-- policy para anon a proposito. Se escribe y se lee con
-- SUPABASE_SERVICE_ROLE_KEY (bypassea RLS).

COMMENT ON TABLE reportes_trading IS
    'Reportes periodicos de trading (quincenal/mensual). Generados por src/trading/analisis_periodico.py, '
    'disparados por scripts/generar_reportes.py (bajo demanda o via Cron Job de Railway).';
