# 01_DEPLOY_IMMUTABLE: Arquitectura de Despliegue

Este documento define la infraestructura inmutable de DepaFix.

## 1. Regla de Oro: Referencia Raíz
Todo código utiliza BASE_DIR definido en config/settings.py.
- Exportar al ejecutar: export PYTHONPATH=$PYTHONPATH:.

## 2. Entorno de Ejecución
- Python 3.x+ con venv.
- Variables de Entorno gestionadas en .env.

## 3. Estado de Despliegue
- Arquitectura: Cloud Native (Desacoplada).
- Seguridad: RLS activo en tablas críticas.

## 4. Auditoría de Salud
Para verificar el sistema:
python3 tests/test_connectivity.py
