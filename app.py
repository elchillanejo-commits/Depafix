from flask import Flask, render_template, request, jsonify, send_file, abort
import os
import uuid
import time
from werkzeug.utils import secure_filename
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# --- Configuración de seguridad (Modo Producción) ---
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24).hex())

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
ALLOWED_EXTENSIONS = {'pdf'}
ESTADOS_COMPRA_VALIDOS = {'pendiente', 'comprado', 'recibido'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


def limpiar_archivos_antiguos(carpeta, horas=24):
    """Elimina archivos en `carpeta` con más de `horas` de antigüedad."""
    ahora = time.time()
    limite = ahora - (horas * 3600)
    if not os.path.isdir(carpeta):
        return
    for nombre in os.listdir(carpeta):
        ruta = os.path.join(carpeta, nombre)
        if not os.path.isfile(ruta):
            continue
        try:
            mtime = os.path.getmtime(ruta)
            if mtime < limite:
                os.remove(ruta)
        except OSError:
            pass


def limpiar_todo():
    limpiar_archivos_antiguos(UPLOAD_FOLDER, 24)
    limpiar_archivos_antiguos(OUTPUT_FOLDER, 24)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validar_proyecto(proyecto):
    if not proyecto or not isinstance(proyecto, str):
        return jsonify({"success": False, "error": "Código de proyecto inválido"}), 400
    if not all(c.isalnum() or c in ('-', '_') for c in proyecto):
        return jsonify({"success": False, "error": "Código de proyecto inválido"}), 400
    return None


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/materiales/<proyecto>')
def get_materiales(proyecto):
    err = validar_proyecto(proyecto)
    if err:
        return err
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        res = supabase.table("proyecto_materiales").select("*").eq("proyecto_codigo", proyecto).execute()
        return jsonify({"success": True, "data": res.data})
    except Exception as e:
        app.logger.error(f"Error get_materiales: {e}")
        return jsonify({"success": False, "error": "Error interno al consultar materiales"}), 500


@app.route('/api/materiales/estado', methods=['POST'])
def actualizar_estado_materiales():
    payload = request.get_json(silent=True) or {}
    proyecto = payload.get("proyecto")
    estado = str(payload.get("estado", "")).strip().lower()
    ids = payload.get("ids")

    err = validar_proyecto(proyecto)
    if err:
        return err

    if estado not in ESTADOS_COMPRA_VALIDOS:
        return jsonify({
            "success": False,
            "error": f"Estado inválido. Usa: {', '.join(sorted(ESTADOS_COMPRA_VALIDOS))}"
        }), 400

    if ids is not None:
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            return jsonify({"success": False, "error": "Lista de ids inválida"}), 400
        if not ids:
            return jsonify({
                "success": True,
                "data": {"actualizados": 0, "estado": estado}
            })

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        consulta = (
            supabase.table("proyecto_materiales")
            .update({"estado_compra": estado})
            .eq("proyecto_codigo", proyecto)
        )
        if ids is not None:
            consulta = consulta.in_("id", ids)
        res = consulta.execute()
        filas = res.data or []
        return jsonify({
            "success": True,
            "data": {"actualizados": len(filas), "estado": estado}
        })
    except Exception as e:
        app.logger.error(f"Error actualizar_estado_materiales: {e}")
        return jsonify({"success": False, "error": "Error interno al actualizar el estado"}), 500


@app.route('/api/procesar', methods=['POST'])
def procesar_pdf():
    if 'pdf' not in request.files:
        return jsonify({"success": False, "error": "No se subió ningún archivo"}), 400

    file = request.files['pdf']
    proyecto = request.form.get('proyecto', 'PRY-TEST')

    err = validar_proyecto(proyecto)
    if err:
        return err

    if file.filename == '':
        return jsonify({"success": False, "error": "Archivo vacío"}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": "Solo se permiten archivos PDF"}), 400

    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file.save(filepath)

    try:
        # TODO: aquí va el procesamiento real del PDF
        # Limpieza automática: borrar archivos > 24h tras generar presupuesto
        limpiar_todo()

        return jsonify({
            "success": True,
            "message": "PDF procesado correctamente (Simulación)",
            "data": {
                "total_real": 1382412,
                "total_cliente": 1935349,
                "archivo_pdf": f"presupuesto_{proyecto}.html",
                "archivo_subido": unique_name,
                "redirect_url": f"/ver_presupuesto/{proyecto}"
            }
        })
    except Exception as e:
        app.logger.error(f"Error procesar_pdf: {e}")
        return jsonify({"success": False, "error": "Error interno al procesar el PDF"}), 500


@app.route('/ver_presupuesto/<proyecto>')
def ver_presupuesto(proyecto):
    err = validar_proyecto(proyecto)
    if err:
        return err

    ruta_html = os.path.join(app.config['OUTPUT_FOLDER'], f"presupuesto_{proyecto}.html")

    ruta_real = os.path.realpath(ruta_html)
    output_real = os.path.realpath(app.config['OUTPUT_FOLDER'])
    if not (ruta_real == output_real or ruta_real.startswith(output_real + os.sep)):
        abort(403)

    if not os.path.exists(ruta_html):
        return jsonify({"success": False, "error": f"No se encontró el presupuesto para {proyecto}"}), 404
    return send_file(ruta_html)


@app.route('/api/estado_compra', methods=['POST'])
def actualizar_estado_compra():
    """Actualiza el campo estado_compra de uno o varios materiales en Supabase."""
    data = request.get_json(silent=True) or {}
    proyecto = data.get('proyecto')
    estado = data.get('estado')

    err = validar_proyecto(proyecto)
    if err:
        return err

    if estado not in ('Pendiente', 'Comprado', 'Recibido'):
        return jsonify({"success": False, "error": "Estado inválido"}), 400

    skus = data.get('skus')
    sku = data.get('sku')

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        if skus and isinstance(skus, list) and len(skus) > 0:
            # Actualización masiva
            for s in skus:
                supabase.table("proyecto_materiales").update({"estado_compra": estado}) \
                    .eq("proyecto_codigo", proyecto).eq("material_sku", s).execute()
            return jsonify({
                "success": True,
                "message": f"{len(skus)} material(es) actualizado(s) a {estado}"
            })
        elif sku:
            # Actualización individual
            supabase.table("proyecto_materiales").update({"estado_compra": estado}) \
                .eq("proyecto_codigo", proyecto).eq("material_sku", sku).execute()
            return jsonify({
                "success": True,
                "message": f"{sku} actualizado a {estado}"
            })
        else:
            return jsonify({"success": False, "error": "Falta sku o skus"}), 400
    except Exception as e:
        app.logger.error(f"Error actualizar_estado_compra: {e}")
        return jsonify({"success": False, "error": "Error interno al actualizar estado de compra"}), 500


@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "error": "El archivo es demasiado grande. Máximo 16 MB."}), 413


if __name__ == '__main__':
    app.run(debug=False, port=5000)
