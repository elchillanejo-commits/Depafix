#!/bin/bash
echo "🧪 Probando /predict con ítem real (Pintura látex)..."
curl -s -X POST https://depafix-predictor-production.up.railway.app/predict \
  -H "Content-Type: application/json" \
  -d '{"departamento":"204","items":[{"descripcion":"Pintura látex","cantidad":50}]}' \
  | python3 -m json.tool
echo ""
echo "📊 Si el valor es > 0, ¡SERVIU está integrado!"
