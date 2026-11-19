from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .config import DEFAULT_DB_PATH

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True)
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
BODY_ALIGNMENT = Alignment(vertical="top", wrap_text=True)
THIN_BORDER = Border(
    left=Side(style="thin", color="D9E2F3"),
    right=Side(style="thin", color="D9E2F3"),
    top=Side(style="thin", color="D9E2F3"),
    bottom=Side(style="thin", color="D9E2F3"),
)
STATE_FILLS = {
    "Al día": PatternFill("solid", fgColor="C6EFCE"),
    "Vacante": PatternFill("solid", fgColor="FFEB9C"),
    "Suspendida": PatternFill("solid", fgColor="FFC7CE"),
    "Pago expirado": PatternFill("solid", fgColor="F4B6B6"),
}
PRIORITY_FILLS = {
    "A": PatternFill("solid", fgColor="F8CBAD"),
    "B": PatternFill("solid", fgColor="FFE699"),
    "C": PatternFill("solid", fgColor="E2EFDA"),
}


def _summary_rows(df: pd.DataFrame, rutas_df: pd.DataFrame, meta: dict[str, Any]) -> list[dict[str, Any]]:
    visitables = int(((~df["es_administracion"]) & (df["bloque"] != "Sin asignar")).sum())
    admin = int(df["es_administracion"].sum())
    estados = df["estado"].value_counts().to_dict()
    bloques = df["bloque"].value_counts().to_dict()
    vacantes = df[(df["es_vacante"]) & (~df["es_administracion"])]
    prioridades = vacantes["prioridad_ready_to_rent"].value_counts().to_dict()
    return [
        {"Indicador": "Propiedades Santiago (filtro estricto)", "Valor": len(df), "Detalle": "Comuna = Santiago; incluye 1 registro administrativo."},
        {"Indicador": "Propiedades visitables", "Valor": visitables, "Detalle": "Excluye el registro administrativo y direcciones sin bloque."},
        {"Indicador": "Registros administrativos", "Valor": admin, "Detalle": "No se incluyen en rutas ni en Ready-to-Rent."},
        {"Indicador": "Al día", "Valor": int(estados.get("Al día", 0)), "Detalle": "Estado normalizado."},
        {"Indicador": "Vacante", "Valor": int(estados.get("Vacante", 0)), "Detalle": "Prioridad comercial Ready-to-Rent."},
        {"Indicador": "Suspendida", "Valor": int(estados.get("Suspendida", 0)), "Detalle": "Revisar con corredor antes de visitar."},
        {"Indicador": "Pago expirado", "Valor": int(estados.get("Pago expirado", 0)), "Detalle": "Cobranza / coordinación previa."},
        {"Indicador": "Bloque 1", "Valor": int(bloques.get("Bloque 1", 0)), "Detalle": "Poniente / Ejército / Blanco Encalada."},
        {"Indicador": "Bloque 2", "Valor": int(bloques.get("Bloque 2", 0)), "Detalle": "Centro Cívico / Histórico."},
        {"Indicador": "Bloque 3", "Valor": int(bloques.get("Bloque 3", 0)), "Detalle": "Oriente / Vicuña Mackenna."},
        {"Indicador": "Paradas únicas de ruta", "Valor": int(meta.get("paradas", 0)), "Detalle": "Direcciones únicas; el 1605 duplicado cuenta una vez."},
        {"Indicador": "Segmentos Google Maps", "Valor": int(meta.get("segmentos", 0)), "Detalle": "Máximo 9 waypoints por URL."},
        {"Indicador": "Vacantes prioridad A", "Valor": int(prioridades.get("A", 0)), "Detalle": "Intervención Ready-to-Rent inmediata."},
        {"Indicador": "Vacantes prioridad B", "Valor": int(prioridades.get("B", 0)), "Detalle": "Requiere levantamiento y presupuesto."},
        {"Indicador": "Vacantes prioridad C", "Valor": int(prioridades.get("C", 0)), "Detalle": "Evaluar caso a caso."},
        {"Indicador": "Coordenadas geocodificadas", "Valor": int(meta.get("geocodificadas", 0)), "Detalle": "Nominatim / OpenStreetMap, uso referencial."},
        {"Indicador": "Paradas sin coordenadas", "Valor": int(meta.get("sin_coordenadas", 0)), "Detalle": "La URL usa dirección textual como fallback."},
    ]


def _quality_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {"Control": "Direcciones sin número", "Filas": int(df["sin_numero"].sum()), "Acción": "Confirmar con corredor antes de salir."},
        {"Control": "Direcciones repetidas", "Filas": int(df["duplicado_direccion"].sum()), "Acción": "Confirmar si son unidades distintas (1605 x2)."},
        {"Control": "Sin superficie", "Filas": int(df["sin_superficie"].sum()), "Acción": "Medir en terreno; cotizar SPC por m²."},
        {"Control": "Sin dormitorios", "Filas": int(df["sin_dormitorios"].sum()), "Acción": "Levantar dormitorios y baños."},
        {"Control": "Sin baños", "Filas": int(df["sin_banos"].sum()), "Acción": "Levantar baños y artefactos."},
        {"Control": "Sin valor de arriendo", "Filas": int(df["sin_valor"].sum()), "Acción": "Validar con corredor; no bloquear visita."},
        {"Control": "Sin antigüedad referencial", "Filas": int(df["antiguedad_estimada_anios"].isna().sum()), "Acción": "Completar catastro o estimar en visita."},
        {"Control": "Requiere revisión previa", "Filas": int(df["requiere_revision"].sum()), "Acción": "Revisar observaciones de la unidad."},
    ]


def _notes_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {"Tema": "Antigüedad", "Nota": "Columna estimada con catastro referencial DepaFix; no se encontró catastro municipal oficial en el entorno. Reemplazar datos/catastro_referencial_stgo_centro.csv por la fuente oficial cuando esté disponible."},
        {"Tema": "Google Maps", "Nota": "Cada segmento respeta el máximo de 9 waypoints. Si hay más paradas, se divide en segmentos con una parada de overlap."},
        {"Tema": "Datos personales", "Nota": "Este entregable excluye RUT, correo y teléfono. Los nombres de propietario/arrendatario quedan solo en la fuente original."},
        {"Tema": "Duplicado 1605", "Nota": "Blanco Encalada 1771 Depto. 1605 aparece dos veces en el origen; una vacante y una al día. Se visita una vez y se confirma si son dos unidades."},
        {"Tema": "Registro administrativo", "Nota": "El registro 'Administración departamentos Santiago Centro' (ID 64395) no es una unidad visitable; queda fuera de rutas y Ready-to-Rent."},
        {"Tema": "Base de datos", "Nota": f"SQLite generado en {DEFAULT_DB_PATH}. Tablas: inspecciones_terreno, presupuestos_obra, log_comunicaciones_corredor."},
    ]


def _style_sheet(ws, freeze: str = "A2", auto_filter: bool = True) -> None:
    ws.freeze_panes = freeze
    ws.sheet_view.showGridLines = False
    if auto_filter and ws.max_row >= 1:
        ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER
    ws.row_dimensions[1].height = 32
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = BODY_ALIGNMENT
            cell.border = THIN_BORDER
    for column in ws.columns:
        letter = get_column_letter(column[0].column)
        max_length = max((len(str(cell.value)) if cell.value is not None else 0) for cell in column)
        ws.column_dimensions[letter].width = min(max(12, max_length + 2), 58)


def _fill_column(ws, header: str, mapping: dict[str, PatternFill]) -> None:
    headers = {cell.value: cell.column for cell in ws[1]}
    column = headers.get(header)
    if not column:
        return
    for row in range(2, ws.max_row + 1):
        value = ws.cell(row=row, column=column).value
        if value in mapping:
            ws.cell(row=row, column=column).fill = mapping[value]


def _hyperlink_column(ws, header: str = "url") -> None:
    headers = {cell.value: cell.column for cell in ws[1]}
    column = headers.get(header)
    if not column:
        return
    for row in range(2, ws.max_row + 1):
        cell = ws.cell(row=row, column=column)
        if cell.value:
            cell.hyperlink = str(cell.value)
            cell.style = "Hyperlink"


def _export_unidades(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "id",
        "estado",
        "prioridad_ready_to_rent",
        "rank_ready_to_rent",
        "bloque",
        "segmento_ruta",
        "parada_ruta",
        "direccion_normalizada",
        "direccion_base",
        "comuna",
        "tipo_propiedad",
        "valor_arriendo_clp",
        "superficie_util_m2",
        "dormitorios",
        "banos",
        "antiguedad_estimada_anios",
        "antiguedad_rango",
        "antiguedad_confianza",
        "accion_ready_to_rent",
        "m2_piso_spc_sugerido",
        "plafones_led_sugeridos",
        "enchufes_sugeridos",
        "soporte_tv_sugerido",
        "unidades_en_direccion",
        "requiere_revision",
        "observaciones",
    ]
    export = df[columns].copy()
    export["rank_ready_to_rent"] = (
        export["rank_ready_to_rent"].astype(object).where(export["rank_ready_to_rent"].notna(), "")
    )
    export["parada_ruta"] = (
        export["parada_ruta"].astype(object).where(export["parada_ruta"].notna(), "")
    )
    return export


def _export_ready(df: pd.DataFrame) -> pd.DataFrame:
    vacantes = df[(df["es_vacante"]) & (~df["es_administracion"])].sort_values(
        ["rank_ready_to_rent", "score_ready_to_rent"], ascending=[True, False]
    )
    columns = [
        "rank_ready_to_rent",
        "prioridad_ready_to_rent",
        "score_ready_to_rent",
        "id",
        "direccion_normalizada",
        "bloque",
        "segmento_ruta",
        "parada_ruta",
        "superficie_util_m2",
        "dormitorios",
        "banos",
        "antiguedad_rango",
        "accion_ready_to_rent",
        "m2_piso_spc_sugerido",
        "m2_piso_spc_estimado",
        "plafones_led_sugeridos",
        "enchufes_sugeridos",
        "soporte_tv_sugerido",
        "uplift_estimado_clp",
        "observaciones",
    ]
    export = vacantes[columns].copy()
    export["rank_ready_to_rent"] = export["rank_ready_to_rent"].astype(object)
    export["parada_ruta"] = export["parada_ruta"].astype(object).where(export["parada_ruta"].notna(), "")
    return export


def write_excel(
    df: pd.DataFrame,
    rutas_df: pd.DataFrame,
    catastro: pd.DataFrame,
    meta: dict[str, Any],
    outpath: Path,
) -> Path:
    summary = pd.DataFrame(_summary_rows(df, rutas_df, meta))
    quality = pd.DataFrame(_quality_rows(df))
    notes = pd.DataFrame(_notes_rows(df))
    unidades = _export_unidades(df)
    ready = _export_ready(df)
    rutas = rutas_df.copy() if not rutas_df.empty else pd.DataFrame(
        columns=["bloque", "segmento", "paradas", "unidades", "primer_parada", "ultima_parada", "waypoints", "metodo", "url"]
    )

    outpath.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(outpath, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Resumen", index=False)
        unidades.to_excel(writer, sheet_name="Unidades", index=False)
        rutas.to_excel(writer, sheet_name="Rutas", index=False)
        ready.to_excel(writer, sheet_name="Ready_to_Rent", index=False)
        quality.to_excel(writer, sheet_name="Calidad_Datos", index=False)
        catastro.to_excel(writer, sheet_name="Catastro_Referencial", index=False)
        notes.to_excel(writer, sheet_name="Notas", index=False)

        workbook = writer.book
        for sheet_name in ("Resumen", "Unidades", "Rutas", "Ready_to_Rent", "Calidad_Datos", "Catastro_Referencial", "Notas"):
            ws = workbook[sheet_name]
            _style_sheet(ws, auto_filter=sheet_name not in {"Resumen", "Notas"})

        _fill_column(workbook["Unidades"], "estado", STATE_FILLS)
        _fill_column(workbook["Ready_to_Rent"], "prioridad_ready_to_rent", PRIORITY_FILLS)
        _hyperlink_column(workbook["Rutas"], "url")

        for sheet_name, columns in {
            "Unidades": ["valor_arriendo_clp", "superficie_util_m2", "m2_piso_spc_sugerido"],
            "Ready_to_Rent": ["superficie_util_m2", "m2_piso_spc_sugerido"],
        }.items():
            ws = workbook[sheet_name]
            headers = {cell.value: cell.column for cell in ws[1]}
            for header in columns:
                column = headers.get(header)
                if column:
                    for row in range(2, ws.max_row + 1):
                        ws.cell(row=row, column=column).number_format = "#,##0.0"

    return outpath


def _md_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_checklist(
    df: pd.DataFrame,
    rutas_df: pd.DataFrame,
    meta: dict[str, Any],
    outpath: Path,
) -> Path:
    vacantes = df[(df["es_vacante"]) & (~df["es_administracion"])].sort_values(
        ["rank_ready_to_rent", "score_ready_to_rent"], ascending=[True, False]
    )
    lines: list[str] = [
        "# CHECKLIST MÓVIL — RUTA TERRENO STGO CENTRO",
        "",
        f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        "**Cobertura:** 50 registros de la comuna de Santiago; 49 visitables y 1 administrativo.  ",
        "**Objetivo:** inspección técnica, validación de agua caliente, evidencias antes/después y levantamiento Ready-to-Rent.",
        "",
        "> No registrar RUT, correo ni teléfono en este documento. La coordinación con propietarios/arrendatarios es responsabilidad del corredor.",
        "",
        "## 1. Rutas por bloque",
        "",
    ]
    if rutas_df.empty:
        lines.append("No se generaron rutas.")
    else:
        for block in ("Bloque 1", "Bloque 2", "Bloque 3"):
            block_routes = rutas_df[rutas_df["bloque"] == block]
            if block_routes.empty:
                continue
            lines.append(f"### {block}")
            lines.append("")
            for _, route in block_routes.iterrows():
                lines.append(
                    f"- [ ] **{route['segmento']}** — {route['paradas']} paradas / {route['unidades']} unidades. "
                    f"[Abrir ruta en Google Maps]({route['url']})"
                )
            lines.append("")

    lines.extend(
        [
            "## 2. Vacantes prioritarias Ready-to-Rent",
            "",
            "| # | Prioridad | Dirección | m² | Dorm/Baño | Acción |",
            "|---|---|---|---|---|---|",
        ]
    )
    for _, row in vacantes.iterrows():
        sup = "s/d" if pd.isna(row["superficie_util_m2"]) else f"{row['superficie_util_m2']:.0f}"
        dorm = None if pd.isna(row["dormitorios"]) else int(row["dormitorios"])
        banos = None if pd.isna(row["banos"]) else int(row["banos"])
        if dorm is None and banos is None:
            dorm_banos = "s/d"
        else:
            dorm_banos = f"{dorm if dorm is not None else 's/d'}/{banos if banos is not None else 's/d'}"
        lines.append(
            f"| {row['rank_ready_to_rent']} | {row['prioridad_ready_to_rent']} | "
            f"{_md_escape(row['direccion_normalizada'])} | {sup} | {dorm_banos} | "
            f"{_md_escape(row['accion_ready_to_rent'])} |"
        )

    lines.extend(
        [
            "",
            "## 3. Antes de salir",
            "",
            "- [ ] Celular cargado + power bank + cable.",
            "- [ ] Google Maps offline del área Santiago Centro descargado.",
            "- [ ] Este checklist y `RUTA_TERRENO_STGO_CENTRO.xlsx` disponibles sin internet.",
            "- [ ] Huincha láser, linterna, guantes y calzado de seguridad.",
            "- [ ] Cámara/celular con fecha y hora activadas.",
            "- [ ] Llaves/accesos coordinados con corredor.",
            "- [ ] Confirmar por WhatsApp las visitas del día y el registro administrativo excluido.",
            "",
            "## 4. Checklist por unidad",
            "",
            "### Acceso y estado",
            "- [ ] Confirmar dirección, torre y departamento.",
            "- [ ] Validar estado: Al día / Vacante / Suspendida / Pago expirado.",
            "- [ ] Registrar nombre del inspector y fecha/hora.",
            "- [ ] Si no hay acceso: marcar `NO_ACCESO` y hora de reintento.",
            "",
            "### Agua caliente (punto cero)",
            "- [ ] Tipo: `TERMO_ELECTRICO` / `CALEFONT` / `CALDERA_CENTRAL`.",
            "- [ ] Si es termo: fecha de última mantención y capacidad.",
            "- [ ] Próxima mantención: 6 meses (estándar) o 12 meses (excepción autorizada).",
            "- [ ] Revisar ánodo de magnesio, sarro, válvula y llave de paso.",
            "- [ ] Si es calefont/caldera: presión, llaves de paso y ventilación.",
            "",
            "### Evidencias",
            "- [ ] Foto antes: tablero eléctrico.",
            "- [ ] Foto antes: sello de tina/lavaplatos y encuentros de piso con muro.",
            "- [ ] Foto antes: estado general de pintura y piso.",
            "- [ ] Video corto 20-30 s recorriendo la unidad.",
            "- [ ] Fotos después si se ejecuta algún ajuste inmediato.",
            "- [ ] Nomenclatura: `ID_DEPTO_ANTES_01.jpg`, `ID_DEPTO_DESPUES_01.jpg`.",
            "",
            "### Requerimientos mayoristas",
            "- [ ] Plafones LED (cantidad y tipo: embutir/sobreponer, 18W/24W).",
            "- [ ] Enchufes y placas (cantidad, Bticino/Legrand).",
            "- [ ] Soporte TV universal (32\"-65\").",
            "- [ ] m² de piso SPC (medir; si no hay dato, estimar y marcar).",
            "- [ ] Silicona neutra antihongo y flexibles de agua/gas.",
            "",
            "### Evaluación Ready-to-Rent",
            "- [ ] Alfombra/flotante agotado o levantado.",
            "- [ ] Pisos que requieren conversión a SPC.",
            "- [ ] Iluminación deficiente o luminarias antiguas.",
            "- [ ] Enchufes insuficientes o sin puesta a tierra.",
            "- [ ] Pintura, sellos y humedad.",
            "",
            "## 5. Cierre post-visita",
            "",
            "- [ ] Insertar/actualizar inspección en `inspecciones_terreno`.",
            "- [ ] Adjuntar rutas de fotos/videos antes y después.",
            "- [ ] Crear `presupuestos_obra` en estado `BORRADOR` si hay remodelación.",
            "- [ ] Registrar contacto del corredor en `log_comunicaciones_corredor`.",
            "- [ ] WhatsApp: `PENDIENTE` / `ENVIADO` / `RESPONDIDO` / `SIN_RESPUESTA`.",
            "- [ ] Llamada: `AGENDADO` / `RECHAZADO` / `CERRADO`.",
            "- [ ] Definir próximo seguimiento y responsable.",
            "",
            "## 6. Base de datos y regeneración",
            "",
            f"- SQLite: `{DEFAULT_DB_PATH}`",
            "- Tablas: `inspecciones_terreno`, `presupuestos_obra`, `log_comunicaciones_corredor`.",
            "- El pipeline deja 49 inspecciones `PENDIENTE` y 1 registro `NO_APLICA`.",
            "",
            "```bash",
            "cd /home/ibar/DepaFix_Maestro",
            "python3 -m operacion_terreno \\",
            "  --xlsx /home/ibar/Descargas/propiedades_11_2026.xlsx \\",
            "  --plan PLAN_RUTA_Y_PRESUPUESTOS_STGO.md \\",
            "  --outdir .",
            "```",
            "",
            "## 7. Notas",
            "",
            f"- Antigüedad: estimación referencial; cobertura de catastro: {meta.get('catastro_cobertura', 's/d')}.",
            "- Google Maps: segmentos de hasta 11 paradas (máximo 9 waypoints); no se repiten paradas entre segmentos.",
            "- El registro administrativo ID 64395 no se visita.",
            "- El departamento 1605 de Blanco Encalada 1771 tiene dos registros; confirmar si son dos unidades.",
            "",
        ]
    )
    outpath.write_text("\n".join(lines), encoding="utf-8")
    return outpath


def write_normalized_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def write_routes_json(rutas_df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rutas_df.to_json(orient="records", force_ascii=False, indent=2))
    return path
