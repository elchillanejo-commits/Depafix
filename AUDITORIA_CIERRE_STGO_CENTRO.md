# Auditoría Final de Operación Terreno, Git y Sincronización Railway — Santiago Centro

## 1. Objetivo de la Revisión (Build)
Verificar de punta a punta la integridad del repositorio `/home/ibar/DepaFix_Maestro`, el estado del árbol Git, la base de datos SQLite local (`datos/terreno_stgo_centro.db`) y la compatibilidad del cliente de sincronización (`operacion_terreno/sync_railway.py`) con el despliegue blindado en Railway (`https://depafix-presupuestos-production.up.railway.app`).

## 2. Puntos de Control Obligatorios
1. **Estado del Repositorio (`git status` / `git diff`):**
   - Auditar los cambios pendientes en `operacion_terreno/gestion_visita.py`, `operacion_terreno/presupuestador.py`, `operacion_terreno/sync_railway.py`, `BUGS.md`, `MATRIZ_COSTOS_Y_SINCRONIZACION_STGO.md` y el archivo sin seguimiento `DASHBOARD_Y_PRESENTACION_CORREDOR.md`.
   - **Regla estricta:** NO tocar ni revertir los cambios externos preexistentes en `app_visitas.py` ni `serviu_precios.yml`.
   - Verificar ausencia total de credenciales o API keys hardcodeadas en el código fuente.
2. **Integridad de SQLite (`datos/terreno_stgo_centro.db`):**
   - Confirmar `PRAGMA integrity_check == 'ok'`.
   - Validar que existan exactamente **50 inspecciones** (49 `PENDIENTE` + 1 `NO_APLICA` correspondiente al registro administrativo ID `64395`) y **7 presupuestos** en estado `SIMULACION_CORREDOR` (3 con `PENDIENTE_MEDICION` y 4 medidos).
   - Confirmar cuadratura financiera exacta en `Decimal`: Costo mayorista `$3.756.300`, Venta neta `$7.652.500`, Comisión 10% `$765.250` y Margen DepaFix `$3.130.950`.
3. **Verificación de CLI y Entregables:**
   - Compilación limpia (`python3 -m py_compile operacion_terreno/*.py`).
   - Ejecución sin mutaciones de `python3 -m operacion_terreno.dashboard` y `python3 -m operacion_terreno.sync_railway --id 64364` (modo `--dry-run` por defecto).
   - Validar que `sync_railway.py` lea `DEPAFIX_API_KEY` desde entorno (`os.getenv`) y envíe el header `X-API-Key` correctamente cuando se use `--send`.
   - Verificar existencia y vigencia de `CHECKLIST_MOVIL.md`, `PROPUESTA_COMERCIAL_CORREDOR.md`, `PROPUESTA_EJECUTIVA_CORREDOR.html` y `RUTA_TERRENO_STGO_CENTRO.xlsx`.

## 3. Criterio de Aprobación
Entregar un diagnóstico ejecutivo corto indicando: qué está listo para commit, qué riesgos residuales quedan (ej. `BUG-026` en API legacy) y los comandos exactos para dejar el commit limpio sin arrastrar `app_visitas.py` ni `serviu_precios.yml`.
