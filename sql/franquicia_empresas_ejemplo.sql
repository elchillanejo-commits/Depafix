insert into public.franquicia_empresas (
    rut_empresa,
    razon_social,
    franquicia_anual,
    usado,
    "año"
)
values (
    '76.123.456-7',
    'Zengin OTEC SpA',
    301500,
    50000,
    extract(year from current_date)::int
)
on conflict (rut_empresa) do update set
    razon_social = excluded.razon_social,
    franquicia_anual = excluded.franquicia_anual,
    usado = excluded.usado,
    "año" = excluded."año",
    updated_at = now();

select
    rut_empresa,
    razon_social,
    franquicia_anual,
    usado,
    disponible,
    "año",
    updated_at
from public.franquicia_empresas
where rut_empresa = '76.123.456-7';
