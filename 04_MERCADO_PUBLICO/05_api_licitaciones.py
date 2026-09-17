#!/usr/bin/env python3
import os
from flask import Flask, request, jsonify
from core.db_manager import DatabaseManager

app = Flask(__name__)
API_KEY = os.getenv("API_KEY_LICITACIONES", "cambia_esta_clave_en_el_env")

def verificar_api_key():
    key = request.headers.get("X-API-Key")
    return key and key == API_KEY

@app.route("/buscar", methods=["GET"])
def buscar():
    if not verificar_api_key():
        return jsonify({"error": "API Key inválida"}), 401
    q = request.args.get("q", "")
    if not q:
        return jsonify({"error": "Falta parámetro 'q'"}), 400
    db = DatabaseManager().get_service_client()
    condiciones = []
    for palabra in q.split():
        condiciones.append(f"titulo ILIKE '%{palabra}%'")
        condiciones.append(f"descripcion ILIKE '%{palabra}%'")
    filtro = " OR ".join(condiciones)
    result = db.table("licitaciones").select("*").or_(filtro).limit(100).execute()
    return jsonify(result.data)

@app.route("/licitacion/<codigo>", methods=["GET"])
def detalle(codigo):
    if not verificar_api_key():
        return jsonify({"error": "API Key inválida"}), 401
    db = DatabaseManager().get_service_client()
    result = db.table("licitaciones").select("*").eq("codigo_licitacion", codigo).execute()
    if not result.data:
        return jsonify({"error": "No encontrada"}), 404
    return jsonify(result.data[0])

@app.route("/status", methods=["GET"])
def status():
    return jsonify({"status": "ok", "message": "API de Licitaciones funcionando"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
