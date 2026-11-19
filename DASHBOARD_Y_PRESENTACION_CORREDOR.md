# Tablero Operativo en Tiempo Real y Presentación Ejecutiva para Corredor — DepaFix

## 1. Propósito del Cierre Operativo
Consolidar la vista de avance de las **50 propiedades de Santiago Centro** (49 visitables + 1 administrativa) y transformar los datos de `datos/terreno_stgo_centro.db` en dos herramientas inmediatas:
1. **Tablero CLI (`operacion_terreno/dashboard.py`):** Vista rápida en terminal del estado de inspecciones (`PENDIENTE`, `REALIZADA`, `NO_ACCESO`), conteo de equipos de agua caliente detectados (`TERMO_ELECTRICO` con alertas de mantención 6/12 meses, `CALEFONT`, `CALDERA_CENTRAL`), presupuestos por estado (`SIMULACION_CORREDOR`, `APROBADO`, `SINCRONIZADO`) y resumen de compra mayorista consolidada (m² SPC, plafones LED, enchufes, soportes TV).
2. **Dossier Ejecutivo HTML/Imprimible (`PROPUESTA_EJECUTIVA_CORREDOR.html`):** Documento visual limpio, corporativo y sin PII, diseñado para proyectar o enviar al corredor en la reunión comercial, mostrando:
   - Resumen financiero de las **7 vacantes Ready-to-Rent** ($7.652.500 venta neta | $765.250 comisión 10% corredor | $3.130.950 margen DepaFix).
   - Comparativa ROI (antes vs. después de piso SPC y luminarias LED).
   - Mapa de rutas por bloques (`B1A`, `B2A`, `B2B`, `B3A`) con enlaces directos a Google Maps.

## 2. Reglas de Implementación
* **Cero PII:** Prohibido incluir nombres, RUT, correos o teléfonos de propietarios/arrendatarios.
* **Cálculos Exactos:** Toda cifra financiera debe operar con `Decimal`.
* **Autocontenido:** El HTML ejecutivo debe tener CSS embebido (sin dependencias externas CDN que fallen offline) y estilos `@media print` listos para guardar como PDF desde el navegador.
* **Integridad:** No modificar `serviu_precios.yml` ni alterar los registros reales de `datos/terreno_stgo_centro.db`.
