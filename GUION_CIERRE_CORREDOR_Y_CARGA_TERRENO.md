# Guion de Reunión con Corredor, Protocolo de Carga Post-Visita y Sincronización Railway

## 1. Guion Directo para Convencer al Corredor (Dueño del 10%)
* **Foco Concreto (No humo):** Mostrarle las **7 unidades vacantes de Santiago Centro** ya presupuestadas en `PROPUESTA_COMERCIAL_CORREDOR.md` (venta neta total **$7.652.500**, comisión corredor **$765.250**, margen DepaFix **$3.130.950** / **40,9%**).
* **Ejemplo estrella (Blanco Encalada 1771, Depto. 1605 — 42 m²):** Cambiar piso desgastado/alfombra por **vinílico SPC**, estandarizar **plafones LED**, **enchufes** y **soporte TV**, más revisión de agua caliente. Menos vacancia y mejor canon de arriendo.
* **Respaldo técnico inapelable:** En cada visita se levantan fotos y videos de **antes y después** + validación de agua caliente (`TERMO_ELECTRICO` cada 6 meses estándar, o máximo 12 meses en excepciones autorizadas; o `CALEFONT` / `CALDERA_CENTRAL`).

## 2. Flujo Operativo de Estados (SQLite -> Aprobación -> Railway)
1. **Nacimiento (`SIMULACION_CORREDOR`):** Presupuestos base generados para las 7 vacantes (3 con `PENDIENTE_MEDICION` hasta medir en terreno).
2. **Carga en Terreno (`BORRADOR` / Actualización):** Al visitar cada unidad (49 visitables en 4 rutas Google Maps: `B1A`, `B2A`, `B2B`, `B3A`), se registran hallazgos, tipo de agua caliente, m² reales y partidas adicionales.
3. **Aprobación (`APROBADO`):** Una vez validado con propietario/corredor, se aprueba el presupuesto local.
4. **Sincronización Railway (`--send`):** Solo los registros `APROBADO` se envían a `https://depafix-presupuestos-production.up.railway.app/api/v1/cotizaciones/` guardando el `uuid` de respuesta en SQLite.

## 3. Reglas de Seguridad y Repositorio
* **Sin PII:** Nunca incluir RUTs, teléfonos, correos ni nombres de arrendatarios/propietarios en reportes ni checklists.
* **Archivos protegidos:** Respetar cambios externos no solicitados (como `serviu_precios.yml`) y mantener `exclude_none=True` en la API.
