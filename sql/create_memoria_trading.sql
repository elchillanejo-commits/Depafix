-- memoria_trading: experiencia acumulada de trading (patrones, condiciones
-- de mercado, resultado real) para BTC/SOL hoy, y cualquier activo futuro
-- (ETH, otras altcoins) sin cambios de esquema -- 'activo' es un campo
-- libre a proposito.
--
-- Se llena EXCLUSIVAMENTE con factores recalculados de datos historicos
-- reales (src/trading/analisis_periodico.py::recomputar_factores_senal +
-- evaluar_resultado) -- nunca con eficacias asumidas o de ejemplo, porque
-- esta tabla puede terminar influyendo en un bot que opera con dinero real.

CREATE TABLE IF NOT EXISTS memoria_trading (
    id BIGSERIAL PRIMARY KEY,
    activo TEXT NOT NULL,
    fecha_senal TIMESTAMPTZ NOT NULL,
    senal TEXT NOT NULL,                  -- COMPRA | VENTA
    condicion_mercado TEXT,               -- tendencia_alcista | tendencia_bajista | rango | desconocido
    patron TEXT NOT NULL,                 -- descripcion generada de los factores realmente presentes
    score_confluencia INT,
    factores JSONB,                       -- {soporte_estatico, fibo_golden_pocket, ema50_test, rsi_extremo, rsi_valor, fvg_presente, order_block_valido, fractal_alineado}
    precio_entrada NUMERIC,
    precio_referencia_24h NUMERIC,
    resultado TEXT NOT NULL DEFAULT 'PENDIENTE',  -- ACIERTO | FALLO | PENDIENTE
    operacion_id TEXT,                    -- id (uuid) de operaciones_ejecutadas, si existe
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT memoria_trading_operacion_id_key UNIQUE (operacion_id)
    -- sin esto, el mismo episodio queda duplicado cada vez que se re-corre un
    -- reporte, y ESPECIALMENTE entre 'quincenal' y 'mensual' -- sus ventanas se
    -- solapan (el mensual incluye los mismos ultimos 14 dias), asi que sin
    -- upsert por operacion_id ambos tipos de reporte re-insertarian las mismas
    -- filas y duplicarian el conteo en generar_recomendaciones().
);

CREATE INDEX IF NOT EXISTS idx_memoria_trading_activo
    ON memoria_trading (activo, fecha_senal DESC);

CREATE INDEX IF NOT EXISTS idx_memoria_trading_patron
    ON memoria_trading (activo, patron);

ALTER TABLE memoria_trading ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE memoria_trading IS
    'Memoria de patrones de trading: un registro por episodio de senal COMPRA/VENTA, con los '
    'factores de confluencia recalculados retroactivamente y el resultado real (precio 24h despues). '
    'Poblada por src/trading/analisis_periodico.py -- nunca con valores de eficacia asumidos.';
