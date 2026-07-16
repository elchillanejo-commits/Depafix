-- velas_cripto: histórico OHLC por activo y temporalidad, para TradingLogic
-- (src/trading/crypto_trader_agent.py). No existía ninguna captura de precios
-- cripto en el proyecto -- este esquema es nuevo, pensado para que un script
-- de ingesta (pendiente, fuera del alcance de hoy) lo alimente desde una API
-- de exchange (ej. klines de Binance). Mientras no haya ingesta real,
-- TradingLogic siempre devuelve ESTADO: ESPERA por falta de datos.
CREATE TABLE IF NOT EXISTS velas_cripto (
    id SERIAL PRIMARY KEY,
    activo TEXT NOT NULL,               -- ej. 'BTC/USDT'
    temporalidad TEXT NOT NULL,         -- '1H' | '4H' | '1D'
    tiempo TIMESTAMPTZ NOT NULL,        -- apertura de la vela
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (activo, temporalidad, tiempo)
);

CREATE INDEX IF NOT EXISTS idx_velas_cripto_lookup
    ON velas_cripto (activo, temporalidad, tiempo DESC);

COMMENT ON TABLE velas_cripto IS
    'Velas OHLC por activo/temporalidad. Consumida por src/trading/crypto_trader_agent.py::TradingLogic. Sin ingesta real todavía -- tabla vacía hasta que exista un pipeline que la llene.';
