from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

COMISION_CORREDOR = Decimal("0.10")
MONEY_QUANT = Decimal("1")


def _d(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def formato_clp(value: Decimal | int | float) -> str:
    return f"${_d(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP):,.0f}".replace(",", ".")


@dataclass(frozen=True)
class ItemCatalogo:
    codigo: str
    nombre: str
    unidad: str
    costo_mayorista: Decimal
    precio_venta: Decimal
    argumento: str

    @property
    def margen_bruto(self) -> Decimal:
        return self.precio_venta - self.costo_mayorista

    @property
    def margen_bruto_pct(self) -> Decimal:
        if self.precio_venta == 0:
            return Decimal("0")
        return (self.margen_bruto / self.precio_venta * 100).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )

    def descripcion(self, cantidad: Decimal) -> str:
        cantidad_txt = f"{cantidad.normalize():f}"
        if "." in cantidad_txt:
            cantidad_txt = cantidad_txt.rstrip("0").rstrip(".")
        return f"{self.codigo} - {self.nombre} ({cantidad_txt} {self.unidad})"


ITEMS: dict[str, ItemCatalogo] = {
    "SPC-001": ItemCatalogo(
        codigo="SPC-001",
        nombre="Piso vinílico SPC 4-5 mm + manta",
        unidad="m²",
        costo_mayorista=Decimal("11500"),
        precio_venta=Decimal("22000"),
        argumento=(
            "Resistente al agua y de rápida instalación; elimina alfombra percudida "
            "y sube el atractivo del aviso. ROI esperado: +$50.000 a +$80.000/mes."
        ),
    ),
    "LED-001": ItemCatalogo(
        codigo="LED-001",
        nombre="Plafón LED circular 18W/24W",
        unidad="un",
        costo_mayorista=Decimal("3200"),
        precio_venta=Decimal("9500"),
        argumento=(
            "Iluminación moderna y de bajo consumo; mejora la percepción visual "
            "en fotografías del portal y reduce consumo eléctrico."
        ),
    ),
    "ELE-001": ItemCatalogo(
        codigo="ELE-001",
        nombre="Módulo enchufe/interruptor Bticino/Legrand",
        unidad="un",
        costo_mayorista=Decimal("2800"),
        precio_venta=Decimal("8500"),
        argumento=(
            "Seguridad eléctrica y cumplimiento normativo; elimina enchufes sueltos "
            "y reduce riesgo de cortocircuito."
        ),
    ),
    "TV-001": ItemCatalogo(
        codigo="TV-001",
        nombre="Soporte TV universal 32\"-65\" + instalación",
        unidad="un",
        costo_mayorista=Decimal("6500"),
        precio_venta=Decimal("18000"),
        argumento=(
            "Evita perforaciones destructivas de arrendatarios en tabiquería y "
            "protege la vida útil del muro."
        ),
    ),
    "TER-001": ItemCatalogo(
        codigo="TER-001",
        nombre="Mantención termo eléctrico (ánodo + purga sarro)",
        unidad="un",
        costo_mayorista=Decimal("12000"),
        precio_venta=Decimal("38000"),
        argumento=(
            "Mantención obligatoria cada 6 meses (máximo 12); evita quema de "
            "resistencia, pérdida de eficiencia y triplicar el gasto eléctrico."
        ),
    ),
    "SIL-001": ItemCatalogo(
        codigo="SIL-001",
        nombre="Sellado perimetral silicona antihongo baño/cocina",
        unidad="gl",
        costo_mayorista=Decimal("4500"),
        precio_venta=Decimal("16000"),
        argumento=(
            "Previene filtraciones a pisos inferiores, humedad y multas de "
            "administración; mejora la terminación percibida."
        ),
    ),
}


@dataclass(frozen=True)
class LineaPresupuesto:
    codigo: str
    desc: str
    unidad: str
    cantidad: Decimal
    precio_unitario: Decimal
    costo_unitario: Decimal
    subtotal_neto: Decimal
    costo_total: Decimal
    margen_bruto: Decimal

    def as_partida(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "desc": self.desc,
            "unidad": self.unidad,
            "cantidad": float(self.cantidad),
            "precio_unitario": float(self.precio_unitario),
            "subtotal_neto": float(self.subtotal_neto),
            "costo_unitario": float(self.costo_unitario),
            "costo_total": float(self.costo_total),
            "margen_bruto": float(self.margen_bruto),
        }

    def as_payload_item(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "desc": self.desc,
            "cantidad": float(self.cantidad),
            "precio": float(self.precio_unitario),
        }


@dataclass(frozen=True)
class CalculoPresupuesto:
    lineas: tuple[LineaPresupuesto, ...]
    total_neto: Decimal
    costo_mayorista: Decimal
    comision_corredor: Decimal
    margen_bruto: Decimal
    margen_depafix: Decimal

    @property
    def margen_bruto_pct(self) -> Decimal:
        if self.total_neto == 0:
            return Decimal("0")
        return (self.margen_bruto / self.total_neto * 100).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )

    @property
    def margen_depafix_pct(self) -> Decimal:
        if self.total_neto == 0:
            return Decimal("0")
        return (self.margen_depafix / self.total_neto * 100).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )

    def partidas(self) -> list[dict[str, Any]]:
        return [linea.as_partida() for linea in self.lineas]

    def payload_items(self) -> list[dict[str, Any]]:
        return [linea.as_payload_item() for linea in self.lineas]


def item(codigo: str) -> ItemCatalogo:
    try:
        return ITEMS[codigo]
    except KeyError as exc:
        raise KeyError(f"Ítem de catálogo no encontrado: {codigo}") from exc


def crear_linea(
    codigo: str,
    desc: str,
    unidad: str,
    cantidad: Decimal | int | float | str,
    precio_unitario: Decimal | int | float | str,
    costo_unitario: Decimal | int | float | str,
) -> LineaPresupuesto:
    cantidad_d = _d(cantidad)
    precio_d = _d(precio_unitario)
    costo_d = _d(costo_unitario)
    if cantidad_d <= 0:
        raise ValueError("La cantidad debe ser mayor a cero.")
    if precio_d <= 0:
        raise ValueError("El precio unitario debe ser mayor a cero.")
    if costo_d < 0:
        raise ValueError("El costo unitario no puede ser negativo.")
    subtotal = _money(precio_d * cantidad_d)
    costo_total = _money(costo_d * cantidad_d)
    return LineaPresupuesto(
        codigo=codigo,
        desc=desc,
        unidad=unidad,
        cantidad=cantidad_d,
        precio_unitario=precio_d,
        costo_unitario=costo_d,
        subtotal_neto=subtotal,
        costo_total=costo_total,
        margen_bruto=_money(subtotal - costo_total),
    )


def linea_personalizada(
    codigo: str,
    desc: str,
    cantidad: Decimal | int | float | str,
    precio_unitario: Decimal | int | float | str,
    costo_unitario: Decimal | int | float | str = 0,
    unidad: str = "un",
) -> LineaPresupuesto:
    codigo = codigo.strip()
    desc = desc.strip()
    if not codigo:
        raise ValueError("El código de la partida ad-hoc no puede estar vacío.")
    if not desc:
        raise ValueError("La descripción de la partida ad-hoc no puede estar vacía.")
    desc_completa = desc if desc.startswith(codigo) else f"{codigo} - {desc}"
    return crear_linea(
        codigo=codigo,
        desc=desc_completa,
        unidad=unidad or "un",
        cantidad=cantidad,
        precio_unitario=precio_unitario,
        costo_unitario=costo_unitario,
    )


def totalizar(lineas: Iterable[LineaPresupuesto]) -> CalculoPresupuesto:
    lineas_tuple = tuple(lineas)
    if not lineas_tuple:
        raise ValueError("El presupuesto no tiene partidas con cantidad mayor a cero.")

    total_neto = _money(sum(linea.subtotal_neto for linea in lineas_tuple))
    costo_mayorista = _money(sum(linea.costo_total for linea in lineas_tuple))
    comision = _money(total_neto * COMISION_CORREDOR)
    margen_bruto = _money(total_neto - costo_mayorista)
    margen_depafix = _money(margen_bruto - comision)
    return CalculoPresupuesto(
        lineas=lineas_tuple,
        total_neto=total_neto,
        costo_mayorista=costo_mayorista,
        comision_corredor=comision,
        margen_bruto=margen_bruto,
        margen_depafix=margen_depafix,
    )


def calcular(requerimientos: Mapping[str, Decimal | int | float | str]) -> CalculoPresupuesto:
    lineas: list[LineaPresupuesto] = []
    for codigo, cantidad_raw in requerimientos.items():
        cantidad = _d(cantidad_raw)
        if cantidad <= 0:
            continue
        catalogo = item(codigo)
        lineas.append(
            crear_linea(
                codigo=catalogo.codigo,
                desc=catalogo.descripcion(cantidad),
                unidad=catalogo.unidad,
                cantidad=cantidad,
                precio_unitario=catalogo.precio_venta,
                costo_unitario=catalogo.costo_mayorista,
            )
        )
    return totalizar(lineas)


def construir_payload(
    direccion: str, comuna: str, calculo: CalculoPresupuesto
) -> dict[str, Any]:
    return {
        "direccion": direccion,
        "comuna": comuna,
        "items": calculo.payload_items(),
        "total_neto": float(calculo.total_neto),
    }
