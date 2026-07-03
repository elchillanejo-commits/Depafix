#!/bin/bash
# Uso: ./listar_deptos.sh <nombre_archivo_json>

ARCHIVO=$1

if [ ! -f "$ARCHIVO" ]; then
    echo "Error: Archivo $ARCHIVO no encontrado."
    exit 1
fi

echo "--- RESUMEN DEPARTAMENTO $(jq -r '.depto' "$ARCHIVO") ---"
echo "Espacios detectados:"
jq -r '.espacios[] | "- \(.nombre): \(.m2) m2"' "$ARCHIVO"
echo "--------------------------"
TOTAL=$(jq -r '[.espacios[].m2] | add' "$ARCHIVO")
echo "TOTAL SUPERFICIE: $TOTAL m2"
