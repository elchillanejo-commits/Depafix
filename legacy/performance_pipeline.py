#!/usr/bin/env python3
"""Pipeline DepaFix de alto rendimiento con profiling, caché MD5 y streaming JSON."""
import os, sys, json, time, hashlib, logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("perf_pipeline")

# --- Streaming JSON ---
def stream_json_array(filepath):
    try:
        import ijson
        with open(filepath, 'rb') as f:
            yield from ijson.items(f, 'item')
    except ImportError:
        logger.warning("ijson no instalado. Usando carga completa (OK para <10k obras).")
        with open(filepath, 'r', encoding='utf-8') as f:
            for item in json.load(f):
                yield item

# --- Profiler ---
class PipelineProfiler:
    def __init__(self):
        self.measurements = {}
    def step(self, name, func, *args, **kwargs):
        t0 = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            dt = time.perf_counter() - t0
            self.measurements[name] = {'duration_sec': round(dt,4), 'status':'OK'}
            logger.info("⏱️  %s: %.3fs", name, dt)
            return result
        except Exception as e:
            dt = time.perf_counter() - t0
            self.measurements[name] = {'duration_sec': round(dt,4), 'status':'FAIL', 'error':str(e)}
            logger.error("❌ %s falló tras %.3fs: %s", name, dt, e)
            raise
    def save_report(self, path='output/performance_report.json'):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'fecha':datetime.now().isoformat(), 'modulos':self.measurements}, f, indent=2, ensure_ascii=False)

# --- Caché MD5 ---
class PredictCache:
    def __init__(self):
        self._cache = {}
    def get(self, filepath):
        md5 = self._file_md5(filepath)
        if md5 is None: return None
        return self._cache.get((os.path.abspath(filepath), md5))
    def put(self, filepath, result):
        md5 = self._file_md5(filepath)
        if md5 is None: return
        self._cache[(os.path.abspath(filepath), md5)] = result
    @staticmethod
    def _file_md5(filepath):
        try:
            h = hashlib.md5()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    h.update(chunk)
            return h.hexdigest()
        except FileNotFoundError:
            return None

# --- Lógica del pipeline ---
def load_nuevas_obras(filepath):
    obras = []
    for item in stream_json_array(filepath):
        obras.append(item)
    logger.info("📥 Obras cargadas: %d", len(obras))
    return obras

def batch_predict(model, obras):
    time.sleep(0.05 * len(obras))  # simula procesamiento
    return [{'id': o.get('id'), 'prediccion': 12345} for o in obras]

def generate_report(obras_con_pred):
    path = 'output/report.json'
    with open(path, 'w') as f:
        json.dump(obras_con_pred, f, indent=2)
    return path

def run_performance_pipeline(nuevas_obras_file='input/nuevas_obras.json'):
    profiler = PipelineProfiler()
    cache = PredictCache()

    logger.info("🏎️  Pipeline Fórmula 1 iniciado")
    try:
        obras = profiler.step('load_obras', load_nuevas_obras, nuevas_obras_file)

        def predict_with_cache():
            cached = cache.get(nuevas_obras_file)
            if cached is not None:
                logger.info("♻️  Usando predicción cacheada")
                return cached
            result = batch_predict(None, obras)
            cache.put(nuevas_obras_file, result)
            return result
        predicciones = profiler.step('batch_predict', predict_with_cache)

        report_path = profiler.step('generate_report', generate_report, predicciones)
        logger.info("📄 Reporte: %s", report_path)
    except Exception as e:
        logger.error("Pipeline abortado: %s", e)
    finally:
        profiler.save_report()
        logger.info("🏁 Pipeline finalizado")

if __name__ == '__main__':
    os.makedirs('input', exist_ok=True)
    os.makedirs('output', exist_ok=True)
    test_file = 'input/nuevas_obras.json'
    if not os.path.exists(test_file):
        obras = [{'id':i, 'nombre':f'Obra {i}', 'm2':100+i} for i in range(1,101)]
        with open(test_file, 'w') as f: json.dump(obras, f)
    run_performance_pipeline(test_file)
