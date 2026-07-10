#!/bin/bash
cd ~/Proyectos/DepaFix
source core/venv/bin/activate
export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 core/api.py
