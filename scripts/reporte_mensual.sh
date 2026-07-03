#!/bin/bash
MES_ANIO=${1:-$(date +%Y-%m)}
OUTPUT="$HOME/informes/informe_$MES_ANIO.pdf"
HTML_TEMP="/tmp/reporte_otec.html"

# Ahora la columna se llama 'fecha' porque la acabamos de crear
TOTAL_CURSOS=$(sqlite3 ~/cursos_sence.db "SELECT count(*) FROM cursos WHERE fecha LIKE '$MES_ANIO%';" 2>/dev/null || echo 0)
TOTAL_PRESUP=$(sqlite3 ~/otec.db "SELECT count(*) FROM presupuestos WHERE fecha LIKE '$MES_ANIO%';" 2>/dev/null || echo 0)
GANANCIA=$(sqlite3 ~/otec.db "SELECT sum(total) FROM presupuestos WHERE fecha LIKE '$MES_ANIO%';" 2>/dev/null || echo 0)

cat > $HTML_TEMP <<EOT
<html><head><style>
    body { font-family: sans-serif; margin: 40px; }
    h1 { color: #2c3e50; border-bottom: 2px solid #3498db; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    td, th { border: 1px solid #ddd; padding: 12px; }
</style></head>
<body>
    <h1>Informe OTEC: $MES_ANIO</h1>
    <table>
        <tr><th>Concepto</th><th>Valor</th></tr>
        <tr><td>Cursos Activos</td><td>${TOTAL_CURSOS:-0}</td></tr>
        <tr><td>Presupuestos Emitidos</td><td>${TOTAL_PRESUP:-0}</td></tr>
        <tr><td>Ganancias Totales</td><td>$ ${GANANCIA:-0}</td></tr>
    </table>
</body></html>
EOT

wkhtmltopdf --quiet "$HTML_TEMP" "$OUTPUT" && echo "✅ Informe generado: $OUTPUT"
rm "$HTML_TEMP"
