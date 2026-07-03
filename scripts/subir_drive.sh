#!/bin/bash
# Script: subir_drive.sh
# Ubicación: ~/depafix/scripts/subir_drive.sh

# 1. Verificar configuración 'gdrive'
if ! rclone listremotes 2>/dev/null | grep -q "^gdrive:"; then
    echo "⚠️ No se encontró el remote 'gdrive'. Iniciando configuración..."
    rclone config
    exit 0
fi

# 2. Buscar respaldo más reciente
RESPALDO=$(ls -t ~/respaldo_otec_*.zip 2>/dev/null | head -1)

if [ -z "$RESPALDO" ]; then
    echo "❌ No se encontró ningún archivo ~/respaldo_otec_*.zip"
    exit 1
fi

echo "📂 Subiendo archivo: $RESPALDO"

# 3. Subir a Drive
if rclone copy "$RESPALDO" "gdrive:OTEC_Respaldos"; then
    echo "✅ ÉXITO: Archivo subido a la carpeta 'OTEC_Respaldos' en Google Drive."
else
    echo "❌ ERROR: Falló la subida a Google Drive."
    exit 1
fi
