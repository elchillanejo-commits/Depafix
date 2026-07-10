#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orquestador del pipeline DepaFix.
Ejecuta en orden: ingesta_automatica.py -> batch_predict.py -> analisis_apu.py.
Detiene el flujo si algún script falla (código de retorno != 0).
Registra tiempos, errores y genera un resumen JSON.
"""

import subprocess
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime

# Importar configuración central
try:
    import config
except ImportError as e:
    print(f"Error: No se pudo importar config.py: {e}", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# Configuración de logging
# =============================================================================
LOG_DIR = Path(getattr(config, 'LOG_DIR', './logs'))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('PipelineOrchestrator')

# =============================================================================
# Funciones auxiliares
# =============================================================================

def run_script(script_path: str, module_name: str) -> dict:
    """
    Ejecuta un script Python y retorna el resultado.
    """
    logger.info(f"Iniciando {module_name} desde {script_path}")
    start_time = time.perf_counter()
    result = {
        'module': module_name,
        'success': False,
        'elapsed': 0.0,
        'returncode': -1,
        'stdout': '',
        'stderr': '',
        'error': None
    }

    try:
        script_file = Path(script_path)
        if not script_file.is_file():
            raise FileNotFoundError(f"Script no encontrado: {script_path}")

        proc = subprocess.run(
            [sys.executable, str(script_file)],
            capture_output=True,
            text=True,
            check=False
        )

        result['returncode'] = proc.returncode
        result['stdout'] = proc.stdout
        result['stderr'] = proc.stderr
        result['success'] = (proc.returncode == 0)

        if not result['success']:
            logger.error(f"{module_name} falló con código {proc.returncode}")
            logger.error(f"stderr: {proc.stderr[:500]}...")
        else:
            logger.info(f"{module_name} completado exitosamente")

    except Exception as e:
        result['error'] = str(e)
        result['success'] = False
        logger.exception(f"Excepción al ejecutar {module_name}: {e}")

    finally:
        result['elapsed'] = time.perf_counter() - start_time
        logger.info(f"{module_name} tomó {result['elapsed']:.2f} segundos")

    return result


def write_summary(summary: dict, output_path: Path):
    """
    Escribe el resumen del pipeline en formato JSON.
    """
    for mod in summary.get('modules', []):
        mod['elapsed'] = round(mod['elapsed'], 3)
        mod.pop('stdout', None)
        mod.pop('stderr', None)
        if mod.get('error'):
            mod['error'] = mod['error'][:200]

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        logger.info(f"Resumen guardado en {output_path}")
    except Exception as e:
        logger.error(f"No se pudo escribir el resumen JSON: {e}")


# =============================================================================
# Orquestador principal
# =============================================================================

def main():
    base_dir = Path(__file__).resolve().parent
    scripts = [
        {'name': 'ingesta_automatica', 'path': base_dir / 'ingesta_automatica.py'},
        {'name': 'batch_predict', 'path': base_dir / 'batch_predict.py'},
        {'name': 'analisis_apu', 'path': base_dir / 'analisis_apu.py'}
    ]

    # Permitir sobreescribir rutas desde config
    if hasattr(config, 'SCRIPT_PATHS'):
        for s in scripts:
            if s['name'] in config.SCRIPT_PATHS:
                s['path'] = Path(config.SCRIPT_PATHS[s['name']])

    pipeline_summary = {
        'timestamp': datetime.now().isoformat(),
        'total_elapsed': 0.0,
        'modules': [],
        'final_status': 'success',
        'message': 'Pipeline completado exitosamente'
    }

    logger.info("=" * 60)
    logger.info("Iniciando pipeline DepaFix")
    logger.info("=" * 60)

    overall_start = time.perf_counter()
    abort = False

    for script in scripts:
        if abort:
            logger.warning(f"Pipeline abortado, no se ejecutará {script['name']}")
            pipeline_summary['modules'].append({
                'module': script['name'],
                'success': False,
                'elapsed': 0.0,
                'returncode': -1,
                'error': 'Pipeline abortado por fallo previo',
                'executed': False
            })
            continue

        result = run_script(str(script['path']), script['name'])
        result['executed'] = True
        pipeline_summary['modules'].append(result)

        if not result['success']:
            abort = True
            pipeline_summary['final_status'] = 'failed'
            pipeline_summary['message'] = f"Fallo en {script['name']} (código {result['returncode']})"
            logger.critical(f"Pipeline interrumpido por fallo en {script['name']}")

    pipeline_summary['total_elapsed'] = time.perf_counter() - overall_start
    logger.info(f"Pipeline finalizado en {pipeline_summary['total_elapsed']:.2f} segundos")
    logger.info(f"Estado final: {pipeline_summary['final_status']}")

    # Guardar resumen JSON
    output_path = Path(getattr(config, 'OUTPUT_DIR', './output')) / 'pipeline_summary.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_summary(pipeline_summary, output_path)

    # Copia con timestamp
    timestamped_path = output_path.parent / f"pipeline_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    write_summary(pipeline_summary, timestamped_path)

    sys.exit(0 if pipeline_summary['final_status'] == 'success' else 1)


if __name__ == "__main__":
    main()
