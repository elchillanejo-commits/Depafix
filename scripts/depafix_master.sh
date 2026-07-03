#!/bin/bash
DB_PATH="$HOME/presupuestos.db"
REPORT_FILE="Reporte_Depafix_$(date +%Y%m%d).txt"
GREEN='\033[0;32m'
NC='\033[0m'

{
    echo "========================================"
    echo " REPORTE DE GESTIÓN DE OBRA - DEPAFIX"
    echo " Fecha: $(date)"
    echo "========================================"
    echo "HITO 1: Definición de Arquitectura (Modelo de Dominio)"
    echo "HITO 2: Implementación de Base de Datos (SQLite)"
    echo "HITO 3: Automatización de Ingesta (CSV/Lote)"
    echo "HITO 4: Consolidación y Reportes de Costos"
    echo "----------------------------------------"
    echo "Resumen Actual por Categoría:"
    sqlite3 -column -header "$DB_PATH" "SELECT categoria, COUNT(*) as cantidad, SUM(costo_por_m2) as total FROM tarifas GROUP BY categoria;"
    echo "========================================"
} > "$REPORT_FILE"

echo "Reporte generado: $REPORT_FILE"
