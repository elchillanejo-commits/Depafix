# 02_MODELO_DATOS_SERVIU: Tabla Maestra

Este archivo documenta la estructura de la tabla 'precios_serviu' en Supabase.

## 1. Definición
- Tabla: precios_serviu
- Propósito: Almacenamiento de valores críticos para cálculos de subsidios y presupuestos.

## 2. Estructura de Datos (verificado contra sql/create_precios_serviu.sql, 2026-07-16)
- id (SERIAL): Identificador único.
- item (Text): Ítem SERVIU/MINVU (DS27).
- unidad (Text): Unidad de medida.
- valor_unitario (Numeric): Precio actual.
- fuente (Text): Origen del dato.
- idempotency_key (Text, UNIQUE): evita duplicados en cargas repetidas.
- created_at (Timestamptz): Registro de creación.

## 3. Acceso
- Documentado como solo lectura vía rol 'bi_readonly' (ver 04_POLITICAS_SEGURIDAD_RLS.md).
- ADVERTENCIA (auditoría 2026-07-16): verificado en vivo contra Supabase, esta tabla
  hoy es legible con la key 'anon' -- el rol 'bi_readonly' documentado aquí todavía
  no está creado ni aplicado como RLS real. Ver docs/00_ESTADO_PRODUCCION.md y
  sql/create_bi_readonly.sql para el estado real y el comando de sincronización.
