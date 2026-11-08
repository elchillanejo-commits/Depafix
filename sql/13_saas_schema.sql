-- 13_saas_schema.sql
-- Esquema SaaS DepaFix: empresas, usuarios, cotizaciones_emitidas
-- Requisitos: UUIDs, FKs con ON DELETE CASCADE, campos JSONB para el payload.
-- Compatible con Supabase (PostgreSQL). Ejecutar en SQL Editor.

begin;

-- Extensión para UUIDs (en Supabase suele estar disponible; gen_random_uuid() también funciona en PG13+)
create extension if not exists pgcrypto;

-- =============================================
-- Tabla: empresas
-- =============================================
create table if not exists public.empresas (
    id uuid primary key default gen_random_uuid(),
    rut text unique,
    razon_social text not null,
    nombre_fantasia text,
    email_contacto text,
    telefono text,
    direccion text,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- =============================================
-- Tabla: usuarios
-- =============================================
create table if not exists public.usuarios (
    id uuid primary key default gen_random_uuid(),
    empresa_id uuid not null references public.empresas(id) on delete cascade,
    email text not null unique,
    nombre text,
    rol text not null default 'user',
    activo boolean not null default true,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_usuarios_empresa_id on public.usuarios(empresa_id);

-- =============================================
-- Tabla: cotizaciones_emitidas
-- =============================================
create table if not exists public.cotizaciones_emitidas (
    id uuid primary key default gen_random_uuid(),
    empresa_id uuid not null references public.empresas(id) on delete cascade,
    usuario_id uuid references public.usuarios(id) on delete cascade,
    folio text,
    estado text not null default 'emitida',
    moneda text not null default 'CLP',
    total_neto numeric(14, 2),
    iva numeric(14, 2),
    total_con_iva numeric(14, 2),
    payload jsonb not null default '{}'::jsonb,
    emitida_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_cotizaciones_emitidas_empresa_id on public.cotizaciones_emitidas(empresa_id);
create index if not exists idx_cotizaciones_emitidas_usuario_id on public.cotizaciones_emitidas(usuario_id);
create index if not exists idx_cotizaciones_emitidas_emitida_at on public.cotizaciones_emitidas(emitida_at desc);

-- =============================================
-- Trigger updated_at (reutilizable)
-- =============================================
create or replace function public.set_updated_at_saas()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists empresas_updated_at on public.empresas;
create trigger empresas_updated_at
before update on public.empresas
for each row execute function public.set_updated_at_saas();

drop trigger if exists usuarios_updated_at on public.usuarios;
create trigger usuarios_updated_at
before update on public.usuarios
for each row execute function public.set_updated_at_saas();

drop trigger if exists cotizaciones_emitidas_updated_at on public.cotizaciones_emitidas;
create trigger cotizaciones_emitidas_updated_at
before update on public.cotizaciones_emitidas
for each row execute function public.set_updated_at_saas();

commit;

-- Verificación rápida (opcional, ejecutar por separado):
-- select table_name from information_schema.tables
-- where table_schema='public' and table_name in ('empresas','usuarios','cotizaciones_emitidas');
