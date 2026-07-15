#!/bin/bash
# Scraper histórico: ejecuta para fechas pasadas
FECHA_INICIO="2026-07-01"
FECHA_FIN="2026-07-14"
RUBRO="Construcción"
mkdir -p datos/historico

for fecha in $(seq $(date -d "$FECHA_INICIO" +%s) 86400 $(date -d "$FECHA_FIN" +%s)); do
    FECHA_STR=$(date -d "@$fecha" +%Y-%m-%d)
    echo "🔍 Scraping para $FECHA_STR..."
    python3 scrapers/mercado_publico.py --rubro "$RUBRO" --estado adjudicada --limite 20 --salida "datos/historico/${RUBRO}_${FECHA_STR}.json"
    sleep 2
done
echo "✅ Histórico completado."
