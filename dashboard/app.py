"""
Dashboard de gestión para DepaFix – Flask + SQLite (corregido)
"""
import sqlite3
import json as _json
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, jsonify as _jsonify

app = Flask(__name__)
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["200/hour", "50/minute"])

DB = "/home/ibar/Proyectos/DepaFix/core/depafix.db"

# ── Plantilla base SIN bloque, usa variable {{ content | safe }} ──
BASE_HTML = '''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>DepaFix Dashboard</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
  <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
    <div class="container">
      <a class="navbar-brand" href="/">⚡ DepaFix</a>
      <div class="collapse navbar-collapse">
        <ul class="navbar-nav me-auto">
          <li class="nav-item"><a class="nav-link" href="/clientes">Clientes</a></li>
          <li class="nav-item"><a class="nav-link" href="/materiales">Materiales</a></li>
          <li class="nav-item"><a class="nav-link" href="/proyectos">Proyectos</a></li>
            <li class="nav-item"><a class="nav-link" href="/cotizar">💰 Cotizador</a></li>
            <li class="nav-item"><a class="nav-link" href="/gantt">📊 Gantt</a></li>
        </ul>
      </div>
    </div>
  </nav>
  <div class="container">
    {{ content | safe }}
  </div>
</body>
</html>'''

def init_db():
    with sqlite3.connect(DB) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                telefono TEXT,
                email TEXT
            );
            CREATE TABLE IF NOT EXISTS materiales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                unidad TEXT,
                precio_unitario REAL
            );
            CREATE TABLE IF NOT EXISTS proyectos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                cliente_id INTEGER,
                fecha_inicio TEXT,
                estado TEXT DEFAULT 'activo',
                FOREIGN KEY(cliente_id) REFERENCES clientes(id)
            );
            CREATE TABLE IF NOT EXISTS partidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proyecto_id INTEGER NOT NULL,
                material_id INTEGER,
                cantidad REAL,
                precio REAL,
                FOREIGN KEY(proyecto_id) REFERENCES proyectos(id),
                FOREIGN KEY(material_id) REFERENCES materiales(id)
            );
        """)

# ── Dashboard ──
@app.route("/")
def index():
    with sqlite3.connect(DB) as conn:
        num_clientes = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
        num_materiales = conn.execute("SELECT COUNT(*) FROM materiales").fetchone()[0]
        num_proyectos = conn.execute("SELECT COUNT(*) FROM proyectos").fetchone()[0]
    contenido = f"""
    <h1>Panel de Control</h1>
    <div class="row mt-4">
      <div class="col-md-4">
        <div class="card text-white bg-primary mb-3">
          <div class="card-body">
            <h5 class="card-title">Clientes</h5>
            <p class="card-text display-4">{num_clientes}</p>
          </div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card text-white bg-success mb-3">
          <div class="card-body">
            <h5 class="card-title">Materiales</h5>
            <p class="card-text display-4">{num_materiales}</p>
          </div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card text-white bg-warning mb-3">
          <div class="card-body">
            <h5 class="card-title">Proyectos activos</h5>
            <p class="card-text display-4">{num_proyectos}</p>
          </div>
        </div>
      </div>
    </div>"""
    return render_template_string(BASE_HTML, content=contenido)

# ── Clientes ──
@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    if request.method == "POST":
        nombre = request.form["nombre"]
        tel = request.form.get("telefono", "")
        email = request.form.get("email", "")
        with sqlite3.connect(DB) as conn:
            conn.execute("INSERT INTO clientes (nombre, telefono, email) VALUES (?,?,?)",
                         (nombre, tel, email))
        return redirect(url_for("clientes"))
    with sqlite3.connect(DB) as conn:
        lista = conn.execute("SELECT * FROM clientes").fetchall()
    # Construir tabla
    filas = ""
    for c in lista:
        filas += f"<tr><td>{c[0]}</td><td>{c[1]}</td><td>{c[2]}</td><td>{c[3]}</td><td><a href='/clientes/eliminar/{c[0]}' class='btn btn-sm btn-danger'>Eliminar</a></td></tr>"
    contenido = f"""
    <h2>Clientes</h2>
    <form method="post" class="row g-3 mb-4">
      <div class="col-md-4"><input name="nombre" placeholder="Nombre" class="form-control" required></div>
      <div class="col-md-3"><input name="telefono" placeholder="Teléfono" class="form-control"></div>
      <div class="col-md-3"><input name="email" placeholder="Email" class="form-control"></div>
      <div class="col-md-2"><button class="btn btn-primary w-100">Agregar</button></div>
    </form>
    <table class="table">
      <thead><tr><th>ID</th><th>Nombre</th><th>Teléfono</th><th>Email</th><th></th></tr></thead>
      <tbody>{filas}</tbody>
    </table>"""
    return render_template_string(BASE_HTML, content=contenido)

@app.route("/clientes/eliminar/<int:id>")
def eliminar_cliente(id):
    with sqlite3.connect(DB) as conn:
        conn.execute("DELETE FROM clientes WHERE id = ?", (id,))
    return redirect(url_for("clientes"))

# ── Materiales ──
@app.route("/materiales", methods=["GET", "POST"])
def materiales():
    if request.method == "POST":
        nombre = request.form["nombre"]
        unidad = request.form.get("unidad", "")
        precio = request.form.get("precio", "0")
        with sqlite3.connect(DB) as conn:
            conn.execute("INSERT INTO materiales (nombre, unidad, precio_unitario) VALUES (?,?,?)",
                         (nombre, unidad, float(precio)))
        return redirect(url_for("materiales"))
    with sqlite3.connect(DB) as conn:
        lista = conn.execute("SELECT * FROM materiales").fetchall()
    filas = ""
    for m in lista:
        filas += f"<tr><td>{m[0]}</td><td>{m[1]}</td><td>{m[2]}</td><td>${m[3]}</td><td><a href='/materiales/eliminar/{m[0]}' class='btn btn-sm btn-danger'>Eliminar</a></td></tr>"
    contenido = f"""
    <h2>Materiales</h2>
    <form method="post" class="row g-3 mb-4">
      <div class="col-md-4"><input name="nombre" placeholder="Nombre del material" class="form-control" required></div>
      <div class="col-md-2"><input name="unidad" placeholder="Unidad (ej. m, kg)" class="form-control"></div>
      <div class="col-md-2"><input name="precio" placeholder="Precio unitario" class="form-control" type="number" step="any"></div>
      <div class="col-md-2"><button class="btn btn-primary w-100">Agregar</button></div>
    </form>
    <table class="table">
      <thead><tr><th>ID</th><th>Nombre</th><th>Unidad</th><th>Precio</th><th></th></tr></thead>
      <tbody>{filas}</tbody>
    </table>"""
    return render_template_string(BASE_HTML, content=contenido)

@app.route("/materiales/eliminar/<int:id>")
def eliminar_material(id):
    with sqlite3.connect(DB) as conn:
        conn.execute("DELETE FROM materiales WHERE id = ?", (id,))
    return redirect(url_for("materiales"))

# ── Proyectos ──
@app.route("/proyectos", methods=["GET", "POST"])
def proyectos():
    if request.method == "POST":
        nombre = request.form["nombre"]
        cliente_id = request.form.get("cliente_id", 0)
        fecha = request.form.get("fecha", datetime.now().strftime("%Y-%m-%d"))
        with sqlite3.connect(DB) as conn:
            conn.execute("INSERT INTO proyectos (nombre, cliente_id, fecha_inicio) VALUES (?,?,?)",
                         (nombre, int(cliente_id) if cliente_id else None, fecha))
        return redirect(url_for("proyectos"))
    with sqlite3.connect(DB) as conn:
        proyectos = conn.execute("SELECT p.id, p.nombre, c.nombre, p.fecha_inicio, p.estado FROM proyectos p LEFT JOIN clientes c ON p.cliente_id = c.id").fetchall()
        clientes = conn.execute("SELECT id, nombre FROM clientes").fetchall()
    filas_proy = ""
    for p in proyectos:
        filas_proy += f"<tr><td>{p[0]}</td><td><a href='/proyecto/{p[0]}'>{p[1]}</a></td><td>{p[2] or '-'}</td><td>{p[3]}</td><td>{p[4]}</td><td><a href='/proyectos/eliminar/{p[0]}' class='btn btn-sm btn-danger'>Eliminar</a></td></tr>"
    opciones_cliente = "<option value=''>Sin cliente</option>"
    for cl in clientes:
        opciones_cliente += f"<option value='{cl[0]}'>{cl[1]}</option>"
    contenido = f"""
    <h2>Proyectos</h2>
    <form method="post" class="row g-3 mb-4">
      <div class="col-md-3"><input name="nombre" placeholder="Nombre del proyecto" class="form-control" required></div>
      <div class="col-md-3">
        <select name="cliente_id" class="form-select">
          {opciones_cliente}
        </select>
      </div>
      <div class="col-md-2"><input name="fecha" type="date" class="form-control"></div>
      <div class="col-md-2"><button class="btn btn-primary w-100">Crear</button></div>
    </form>
    <table class="table">
      <thead><tr><th>ID</th><th>Proyecto</th><th>Cliente</th><th>Inicio</th><th>Estado</th><th></th></tr></thead>
      <tbody>{filas_proy}</tbody>
    </table>"""
    return render_template_string(BASE_HTML, content=contenido)

@app.route("/proyectos/eliminar/<int:id>")
def eliminar_proyecto(id):
    with sqlite3.connect(DB) as conn:
        conn.execute("DELETE FROM proyectos WHERE id = ?", (id,))
    return redirect(url_for("proyectos"))

@app.route("/proyecto/<int:id>")
def detalle_proyecto(id):
    with sqlite3.connect(DB) as conn:
        proy = conn.execute("SELECT p.id, p.nombre, c.nombre, p.fecha_inicio, p.estado FROM proyectos p LEFT JOIN clientes c ON p.cliente_id = c.id WHERE p.id = ?", (id,)).fetchone()
        partidas = conn.execute("SELECT pt.id, m.nombre, pt.cantidad, pt.precio FROM partidas pt LEFT JOIN materiales m ON pt.material_id = m.id WHERE pt.proyecto_id = ?", (id,)).fetchall()
        materiales = conn.execute("SELECT id, nombre FROM materiales").fetchall()
    total = sum(p[3] for p in partidas if p[3]) if partidas else 0
    filas_part = ""
    for p in partidas:
        filas_part += f"<tr><td>{p[1] or 'N/A'}</td><td>{p[2]}</td><td>${p[3]}</td></tr>"
    opciones_mat = ""
    for m in materiales:
        opciones_mat += f"<option value='{m[0]}'>{m[1]}</option>"
    contenido = f"""
    <h2>Proyecto: {proy[1]}</h2>
    <p><strong>Cliente:</strong> {proy[2] or 'Sin asignar'} | <strong>Inicio:</strong> {proy[3]} | <strong>Estado:</strong> {proy[4]}</p>
    <h4>Partidas (presupuesto)</h4>
    <table class="table">
      <thead><tr><th>Material</th><th>Cantidad</th><th>Precio</th></tr></thead>
      <tbody>{filas_part}</tbody>
      <tfoot><tr><th colspan="2">Total</th><th>${total}</th></tr></tfoot>
    </table>
    <h5>Agregar partida</h5>
    <form method="post" action="/proyecto/{proy[0]}/partida" class="row g-2">
      <div class="col-md-4">
        <select name="material_id" class="form-select">
          {opciones_mat}
        </select>
      </div>
      <div class="col-md-2"><input name="cantidad" class="form-control" placeholder="Cantidad" type="number" step="any" required></div>
      <div class="col-md-2"><input name="precio" class="form-control" placeholder="Precio" type="number" step="any" required></div>
      <div class="col-md-2"><button class="btn btn-success w-100">Añadir</button></div>
    </form>
    <a href="/proyectos" class="btn btn-secondary mt-3">Volver</a>"""
    return render_template_string(BASE_HTML, content=contenido)

@app.route("/proyecto/<int:id>/partida", methods=["POST"])
def agregar_partida(id):
    mat_id = request.form["material_id"]
    cantidad = request.form["cantidad"]
    precio = request.form["precio"]
    with sqlite3.connect(DB) as conn:
        conn.execute("INSERT INTO partidas (proyecto_id, material_id, cantidad, precio) VALUES (?,?,?,?)",
                     (id, mat_id, float(cantidad), float(precio)))
    return redirect(url_for("detalle_proyecto", id=id))


# ══════════════════════════════════════════════════════════════════════
# COTIZADOR DEPAFIX — Arquitecto Senior 2026-07-05
# ══════════════════════════════════════════════════════════════════════

TARIFAS_PATH = "../core/tarifas_depafix.json"

# Cache en memoria — carga una sola vez al iniciar
try:
    with open(TARIFAS_PATH) as f:
        _TARIFAS_CACHE = _json.load(f)
except Exception:
    _TARIFAS_CACHE = {}

def _load_tarifas():
    return _TARIFAS_CACHE

HTML_COTIZADOR = """
{% extends base %}
{% block content %}
<div class="row mb-4">
  <div class="col">
    <h2>🧮 Cotizador de Obras</h2>
    <p class="text-muted">Estimación de costos basada en 190 presupuestos históricos DepaFix</p>
  </div>
</div>
<div class="row">
  <div class="col-md-4">
    <div class="card shadow-sm">
      <div class="card-header bg-dark text-white"><b>Calcular cotización</b></div>
      <div class="card-body">
        <div class="mb-3">
          <label class="form-label">Tarea</label>
          <select class="form-select" id="tarea">
            <option value="pintura">Pintura 🟢 Alta confianza</option>
            <option value="sellos">Sellos 🟡 Media confianza</option>
            <option value="electricidad">Electricidad 🟡 Media confianza</option>
            <option value="gasfiteria">Gasfitería 🟡 Media confianza</option>
            <option value="ceramica">Cerámica 🔴 Baja confianza</option>
            <option value="tabiqueria">Tabiquería 🔴 Baja confianza</option>
            <option value="aseo">Aseo 🔴 Baja confianza</option>
          </select>
        </div>
        <div class="mb-3">
          <label class="form-label">Metros cuadrados (m²)</label>
          <input type="number" class="form-control" id="m2input" min="1" max="500" value="50" placeholder="ej: 50">
        </div>
        <button class="btn btn-dark w-100" onclick="cotizar()">💰 Calcular</button>
      </div>
    </div>
  </div>
  <div class="col-md-8">
    <div id="resultado" class="d-none">
      <div class="card shadow-sm border-0">
        <div class="card-header bg-dark text-white d-flex justify-content-between">
          <span><b id="res-tarea"></b></span>
          <span class="badge" id="res-conf-badge"></span>
        </div>
        <div class="card-body">
          <div class="row text-center mb-3">
            <div class="col">
              <div class="text-muted small">OPTIMISTA</div>
              <div class="fs-5 text-success fw-bold" id="res-opt"></div>
            </div>
            <div class="col border-start border-end">
              <div class="text-muted small">ESTIMADO</div>
              <div class="fs-3 fw-bold text-dark" id="res-est"></div>
            </div>
            <div class="col">
              <div class="text-muted small">PESIMISTA</div>
              <div class="fs-5 text-danger fw-bold" id="res-pes"></div>
            </div>
          </div>
          <div class="progress mb-2" style="height:8px">
            <div class="progress-bar bg-success" id="prog-opt" style="width:0%"></div>
            <div class="progress-bar bg-dark"    id="prog-est" style="width:0%"></div>
            <div class="progress-bar bg-danger"  id="prog-pes" style="width:0%"></div>
          </div>
          <div class="row text-center small text-muted mt-3">
            <div class="col" id="res-clpm2"></div>
            <div class="col" id="res-n"></div>
            <div class="col" id="res-disp"></div>
          </div>
          <hr>
          <div id="alerta-conf" class="alert alert-warning small d-none">
            ⚠️ Confianza BAJA: rango amplio de variación. Validar con presupuesto detallado.
          </div>
        </div>
      </div>
    </div>
    <div id="sin-resultado" class="text-center text-muted py-5">
      <div style="font-size:3rem">🧮</div>
      <p>Ingresa m² y tarea para calcular</p>
    </div>
  </div>
</div>

<script>
function fmt(n){ return '$' + Math.round(n).toLocaleString('es-CL'); }
function cotizar(){
  const m2 = document.getElementById('m2input').value;
  const tarea = document.getElementById('tarea').value;
  fetch('/api/cotizar?m2='+m2+'&tarea='+tarea)
    .then(r=>r.json())
    .then(d=>{
      if(d.error){ alert(d.error); return; }
      document.getElementById('resultado').classList.remove('d-none');
      document.getElementById('sin-resultado').classList.add('d-none');
      document.getElementById('res-tarea').textContent = tarea.charAt(0).toUpperCase()+tarea.slice(1)+' — '+m2+'m²';
      document.getElementById('res-est').textContent = fmt(d.estimado);
      document.getElementById('res-opt').textContent = fmt(d.optimista);
      document.getElementById('res-pes').textContent = fmt(d.pesimista);
      document.getElementById('res-clpm2').textContent = 'CLP/m²: '+fmt(d.estimado/m2);
      document.getElementById('res-n').textContent = 'Base: '+d.n_muestras+' obras';
      document.getElementById('res-disp').textContent = 'Dispersión: '+d.dispersion_pct+'%';
      const total = d.pesimista;
      document.getElementById('prog-opt').style.width = (d.optimista/total*100)+'%';
      document.getElementById('prog-est').style.width = ((d.estimado-d.optimista)/total*100)+'%';
      document.getElementById('prog-pes').style.width = ((d.pesimista-d.estimado)/total*100)+'%';
      const badge = document.getElementById('res-conf-badge');
      badge.textContent = d.confianza;
      badge.className = 'badge ' + (d.confianza==='ALTA'?'bg-success':d.confianza==='MEDIA'?'bg-warning text-dark':'bg-danger');
      document.getElementById('alerta-conf').classList.toggle('d-none', d.confianza==='ALTA');
    }).catch(e=>alert('Error: '+e));
}
document.getElementById('m2input').addEventListener('keydown', e=>{if(e.key==='Enter') cotizar();});
</script>
{% endblock %}
"""

@app.route("/cotizar")
def cotizar_page():
    return render_template_string(
        HTML_COTIZADOR.replace("{% extends base %}", "").replace("{% block content %}", "").replace("{% endblock %}", ""),
        **{"base": BASE_HTML}
    )

@app.route("/api/cotizar")
def api_cotizar():
    TAREAS_VALIDAS = {"pintura","ceramica","sellos","aseo","electricidad","gasfiteria","tabiqueria"}
    tarea = request.args.get("tarea","").lower()
    if tarea and tarea not in TAREAS_VALIDAS:
        return _jsonify({"error": f"Tarea invalida. Opciones: {sorted(TAREAS_VALIDAS)}"}), 400
    try:
        m2    = float(request.args.get("m2", 0))
        tarea = request.args.get("tarea", "").lower()
        T     = _load_tarifas()
        if tarea not in T:
            return _jsonify({"error": f"Tarea no valida. Opciones: {sorted(T.keys())}"}), 400
        if not (1 <= m2 <= 500):
            return _jsonify({"error": "m2 debe estar entre 1 y 500"}), 400
        t    = T[tarea]
        conf = "BAJA" if t["mae_pct"]>100 else "MEDIA" if t["mae_pct"]>70 else "ALTA"
        return _jsonify({
            "tarea": tarea, "m2": m2,
            "estimado":      round(m2 * t["media"]),
            "optimista":     round(m2 * t["p10"]),
            "pesimista":     round(m2 * t["p90"]),
            "confianza":     conf,
            "n_muestras":    t["n"],
            "dispersion_pct": round(t["mae_pct"], 1)
        })
    except Exception as e:
        return _jsonify({"error": str(e)}), 500

@app.route("/api/tarifas")
def api_tarifas():
    return _jsonify(_load_tarifas())
# ══ FIN COTIZADOR ══════════════════════════════════════════════════════


@app.route("/gantt")
def gantt():
    from flask import send_file
    return send_file("templates/gantt_depafix.html")

if __name__ == "__main__":
    init_db()
    app.run(debug=False, host="0.0.0.0", port=5050)
