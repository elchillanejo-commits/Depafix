-- 14_add_unique_constraint.sql
-- DepaFix: evita SKUs duplicados por retailer en public.productos.
-- Requisito: ejecutar DESPUÉS de limpiar duplicados existentes
--   (scripts/fix_sku_duplicados.sql). A la fecha 2026-11-07 hay 0 duplicados.
-- Idempotente: se omite si la restricción ya existe.

begin;

do $$
begin
    if not exists (
        select 1
        from pg_constraint c
        join pg_class t on t.oid = c.conrelid
        join pg_namespace n on n.oid = t.relnamespace
        where c.conname = 'productos_sku_retailer_id_key'
          and n.nspname = 'public'
          and t.relname = 'productos'
    ) then
        alter table public.productos
            add constraint productos_sku_retailer_id_key
            unique (sku, retailer_id);
    end if;
end
$$;

commit;

-- Verificación (opcional):
-- select conname, contype
-- from pg_constraint c join pg_class t on t.oid=c.conrelid
-- where t.relname='productos' and conname='productos_sku_retailer_id_key';
