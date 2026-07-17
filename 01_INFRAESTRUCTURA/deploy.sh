#!/bin/bash
docker compose down 2>/dev/null
docker compose build
docker compose up -d
sleep 5
echo "✅ DepaFix dockerizado: http://localhost:80 (frontend) http://localhost:8000 (API)"
