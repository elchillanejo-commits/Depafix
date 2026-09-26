"""properties.py — Genera página HTML con propiedades desde Supabase."""
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
logger = logging.getLogger(__name__)


async def properties_page_worker(params: dict) -> dict:
    """
    Genera HTML con propiedades activas.
    
    Params:
        comuna: filtrar por comuna (opcional)
        precio_max: precio máximo CLP (opcional)
    """
    comuna = params.get("comuna")
    precio_max = params.get("precio_max")

    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )

    query = client.table("properties").select("*").eq("activa", True)
    if comuna:
        query = query.eq("comuna", comuna)
    if precio_max:
        query = query.lte("precio_clp", precio_max)
    query = query.order("precio_clp", desc=False).limit(50)

    resp = query.execute()
    propiedades = resp.data or []

    # Generar HTML
    cards_html = ""
    for p in propiedades:
        precio_fmt = f"${p['precio_clp']:,}".replace(",", ".")
        cards_html += f"""
        <div class="card">
            <div class="card-header">
                <span class="badge">{p.get('comuna', 'N/A')}</span>
            </div>
            <h3>{p.get('titulo', 'Sin título')}</h3>
            <div class="precio">{precio_fmt} CLP/mes</div>
            <div class="detalles">
                <span>🛏️ {p.get('dormitorios', '?')}D</span>
                <span>🚿 {p.get('banos', '?')}B</span>
                <span>📐 {p.get('m2', '?')} m²</span>
            </div>
            <p class="direccion">📍 {p.get('direccion', '')}</p>
            <p class="descripcion">{p.get('descripcion', '')}</p>
            <a href="{p.get('url', '#')}" class="btn">Ver más</a>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Propiedades | DepaFix</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            padding: 2rem;
        }}
        h1 {{ color: #58a6ff; margin-bottom: 1rem; }}
        .stats {{ color: #8b949e; margin-bottom: 2rem; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.5rem;
        }}
        .card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.5rem;
            transition: border-color 0.2s;
        }}
        .card:hover {{ border-color: #58a6ff; }}
        .badge {{
            background: #1f6feb;
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        h3 {{ color: #f0f6fc; margin: 1rem 0 0.5rem 0; font-size: 1.1rem; }}
        .precio {{ color: #3fb950; font-size: 1.4rem; font-weight: 700; margin: 0.5rem 0; }}
        .detalles {{
            display: flex;
            gap: 1rem;
            margin: 0.75rem 0;
            color: #8b949e;
            font-size: 0.9rem;
        }}
        .direccion {{ color: #8b949e; font-size: 0.9rem; margin: 0.5rem 0; }}
        .descripcion {{ color: #8b949e; font-size: 0.85rem; margin: 0.5rem 0 1rem 0; }}
        .btn {{
            display: inline-block;
            background: #238636;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.9rem;
        }}
        .btn:hover {{ background: #2ea043; }}
        footer {{ margin-top: 3rem; color: #484f58; text-align: center; font-size: 0.85rem; }}
    </style>
</head>
<body>
    <h1>🏠 Propiedades DepaFix</h1>
    <div class="stats">
        {len(propiedades)} propiedades activas
        {f'· Comuna: {comuna}' if comuna else '· Todas las comunas'}
        {f'· Hasta ${precio_max:,}'.replace(',', '.') if precio_max else ''}
    </div>
    <div class="grid">
        {cards_html if cards_html else '<p>No hay propiedades con esos filtros.</p>'}
    </div>
    <footer>Generado por CEO Service · {datetime.now(timezone.utc).isoformat()[:19]}</footer>
</body>
</html>"""

    return {
        "ok": True,
        "total": len(propiedades),
        "html": html,
        "chars_html": len(html),
        "ejecutado": datetime.now(timezone.utc).isoformat(),
    }
