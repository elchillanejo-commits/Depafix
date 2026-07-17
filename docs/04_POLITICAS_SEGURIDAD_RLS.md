# 04_POLITICAS_SEGURIDAD_RLS: Indestructible

Políticas de seguridad nivel fila (RLS) para proteger los activos críticos.

## 1. Blindaje
- Activado: ALTER TABLE ... ENABLE ROW LEVEL SECURITY.
- Política: Acceso exclusivo para lectura mediante rol 'bi_readonly'.
- Tablas cubiertas por esta política: presupuestos, precios_serviu, velas_cripto.

## 2. Estado real (auditoría 2026-07-16, verificado en vivo contra Supabase)
- NO SINCRONIZADO. Las 3 tablas de arriba son legibles hoy con la key 'anon'
  pública -- el rol 'bi_readonly' descrito en esta política todavía no existe
  en la base de datos real.
- Comando de sincronización: sql/create_bi_readonly.sql (crea el rol, revoca
  el acceso de 'anon' y aplica la policy de solo-SELECT para bi_readonly).
  Correr en el SQL Editor de Supabase con permisos de owner.
- Ver docs/00_ESTADO_PRODUCCION.md para el detalle completo de riesgos.
