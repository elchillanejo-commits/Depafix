-- Crear tabla ceo_predictions para el predictor del CEO
CREATE TABLE IF NOT EXISTS ceo_predictions (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ DEFAULT now(),
  source TEXT NOT NULL,
  target TEXT NOT NULL,
  patron TEXT NOT NULL,           -- 'trend_latency' | 'degradacion' | 'freq_warn'
  severidad TEXT NOT NULL,        -- 'info' | 'warn'
  detalle TEXT,
  resultado_real TEXT,            -- nullable, para validación futura
  verificado_en TIMESTAMPTZ       -- nullable
);

CREATE INDEX IF NOT EXISTS idx_ceo_predictions_source_target_ts ON ceo_predictions(source, target, ts DESC);
