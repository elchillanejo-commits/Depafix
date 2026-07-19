-- 01_velas_cripto
CREATE TABLE IF NOT EXISTS velas_cripto (
    id BIGSERIAL PRIMARY KEY,
    par TEXT NOT NULL,
    temporalidad TEXT NOT NULL,
    tiempo TIMESTAMPTZ NOT NULL,
    apertura NUMERIC NOT NULL,
    maximo NUMERIC NOT NULL,
    minimo NUMERIC NOT NULL,
    cierre NUMERIC NOT NULL,
    volumen NUMERIC NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(par, temporalidad, tiempo)
);

CREATE INDEX IF NOT EXISTS idx_velas_cripto_par_tiempo ON velas_cripto(par, tiempo DESC);
CREATE INDEX IF NOT EXISTS idx_velas_cripto_par_temporalidad ON velas_cripto(par, temporalidad);
CREATE INDEX IF NOT EXISTS idx_velas_cripto_tiempo ON velas_cripto(tiempo);
