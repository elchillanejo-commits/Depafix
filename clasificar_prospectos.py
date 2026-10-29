#!/usr/bin/env python3
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
RUTA_CSV = BASE_DIR / "prospectos.csv"
RUTA_TXT = BASE_DIR / "prospectos.txt"
RUTA_SALIDA = BASE_DIR / "resultados_clasificados.csv"

MANUAL_VENTA = {
    '1w9': ('Marco Aurelio', [
        (r'\bcauto\b', 3), (r'\bcontador\b', 3), (r'\bde esfuerzo\b', 3), (r'\bdios\b', 2),
        (r'\bcorrecto\b', 2), (r'\bordenado\b', 2), (r'\betico\b', 2), (r'\bresponsable\b', 2),
        (r'\bestructurado\b', 2), (r'\bdetallista\b', 2), (r'\bperfeccionista\b', 3),
        (r'\bbuen tipo\b', 1), (r'\bbuena persona\b', 1), (r'\bestable\b', 1), (r'\btrabajador\b', 1)]),
    '2w3': ('San Francisco', [
        (r'\bsolidario\b', 4), (r'\bservicial\b', 4), (r'\balegre\b', 3), (r'\bsonriente\b', 3),
        (r'\bbuena persona\b', 3), (r'\bbuena mujer\b', 3), (r'\bbuen muchacho\b', 3),
        (r'\bexcelente trato\b', 4), (r'\bmedico\b', 3), (r'\bprestigioso\b', 2),
        (r'\bprofesor\b', 3), (r'\bkinesiolog', 3), (r'\bempatico\b', 4), (r'\bcuidado\b', 2),
        (r'\bsimpatico\b', 2), (r'\bbuen tipo\b', 2), (r'\bfamilia\b', 1)]),
    '3w2': ('Maquiavelo', [
        (r'\bimagen\b', 3), (r'\bredes sociales\b', 3), (r'\bfama\b', 3), (r'\bpopularidad\b', 3),
        (r'\bnegociador\b', 3), (r'\bnegocios\b', 2), (r'\bcompetitivo\b', 3), (r'\bbusca ganar\b', 3),
        (r'\bganar\b', 2), (r'\binversor\b', 3), (r'\bexito\b', 3), (r'\bambicioso\b', 3),
        (r'\bplata\b', 1), (r'\bdinero\b', 1), (r'\bsuperficial\b', 2), (r'\balumbrad', 2),
        (r'\binsegura\b', 1), (r'\bextrovertid', 1), (r'\bcomerciante\b', 2), (r'\bventas\b', 2)]),
    '4w5': ('Nietzsche', [
        (r'\bfotografo\b', 4), (r'\bcantante\b', 3), (r'\bartista\b', 4), (r'\bcreativo\b', 4),
        (r'\bmusico\b', 4), (r'\bdisenador\b', 4), (r'\bespecial\b', 2), (r'\bunico\b', 3),
        (r'\bautentico\b', 3), (r'\bdepresivo\b', 3), (r'\bsolitario\b', 2), (r'\bsensible\b', 2)]),
    '5w6': ('Descartes', [
        (r'\btimid[oa]?\b.*\binteligente\b', 5), (r'\binteligente\b.*\btimid[oa]?\b', 5),
        (r'\bintrovertid[oa]?\b.*\binteligente\b', 4), (r'\binteligente\b.*\bintrovertid[oa]?\b', 4),
        (r'\breservado\b', 3), (r'\bmisterioso\b', 3), (r'\bno deja entrar\b', 4),
        (r'\bdificil de entrar\b', 3), (r'\bobservador\b', 3), (r'\banalitico\b', 4),
        (r'\btecnico\b', 3), (r'\binformatic', 3), (r'\bingener', 2), (r'\bcontador\b', 2),
        (r'\bzorro\b', 1), (r'\bpillo\b', 1)]),
    '6w5': ('Séneca', [
        (r'\bleal\b', 5), (r'\bprudente\b', 4), (r'\bcauto\b', 3), (r'\bdesconfiado\b', 4),
        (r'\bmacabeo\b', 4), (r'\bmiedo\b', 3), (r'\binseguro\b', 3), (r'\bseguridad\b', 4),
        (r'\bno presta plata\b', 4), (r'\baustero\b', 3), (r'\bfamilia\b', 1), (r'\bestable\b', 1)]),
    '7w8': ('Epicuro', [
        (r'\bdivertido\b', 4), (r'\bchistoso\b', 4), (r'\bconversador\b', 4), (r'\bvariedad\b', 4),
        (r'\bmovimiento\b', 3), (r'\bestimulo\b', 3), (r'\bosado\b', 3), (r'\bloc[ao]\b', 3),
        (r'\bdiversion\b', 4), (r'\balcohol\b', 2), (r'\baventurero\b', 4), (r'\boptimista\b', 4),
        (r'\bpub\b', 2), (r'\bviajero\b', 4), (r'\bsimpatico\b', 2), (r'\bextrovertid', 1)]),
    '8w7': ('Sun Tzu', [
        (r'\bviolento\b', 5), (r'\bfrontal\b', 4), (r'\bdirecto\b', 3), (r'\bcompetitivo\b', 3),
        (r'\bcontrol\b', 3), (r'\bdominante\b', 4), (r'\blider\b', 4), (r'\bpopular\b', 2),
        (r'\bosado\b', 2), (r'\bintenso\b', 3), (r'\bfuerte\b', 3), (r'\bdecide rapido\b', 4),
        (r'\bfuera de control\b', 4), (r'\bsoldado\b', 2), (r'\bpadre solvente\b', 2)]),
    '9w1': ('Lao Tsé', [
        (r'\btranquil[oa]\b', 4), (r'\bbuena onda\b', 5), (r'\bpacifico\b', 4),
        (r'\bconciliador\b', 4), (r'\bevita conflicto\b', 5), (r'\bpasivo\b', 4),
        (r'\bcalma\b', 3), (r'\bsin presion\b', 4), (r'\bheredero\b', 3),
        (r'\bpoca red\b', 3), (r'\bno se sabe mucho\b', 3)]),
}
REGLAS_INFO_CLAVE = [('bolsa', '5w6', 'Descartes'), ('insumos', '6w5', 'Séneca'), ('acero', '8w7', 'Sun Tzu'), ('totems', '7w8', 'Epicuro'), ('otec', '2w3', 'San Francisco')]
REGLAS_RUBRO = [('abogado', '1w9', 'Marco Aurelio'), ('legal', '1w9', 'Marco Aurelio'), ('odontolog', '1w9', 'Marco Aurelio'), ('medic', '2w3', 'San Francisco'), ('salud', '2w3', 'San Francisco'), ('kinesiolog', '2w3', 'San Francisco'), ('restoran', '2w3', 'San Francisco'), ('restaurante', '2w3', 'San Francisco'), ('comida', '2w3', 'San Francisco'), ('gastronom', '2w3', 'San Francisco'), ('comerciante', '3w2', 'Maquiavelo'), ('ventas', '3w2', 'Maquiavelo'), ('comercial', '3w2', 'Maquiavelo'), ('arriendo', '3w2', 'Maquiavelo'), ('comision', '3w2', 'Maquiavelo'), ('contactos', '3w2', 'Maquiavelo'), ('muebles', '4w5', 'Nietzsche'), ('ropa', '4w5', 'Nietzsche'), ('moda', '4w5', 'Nietzsche'), ('arte', '4w5', 'Nietzsche'), ('diseno', '4w5', 'Nietzsche'), ('musica', '4w5', 'Nietzsche'), ('fotograf', '4w5', 'Nietzsche'), ('productora', '4w5', 'Nietzsche'), ('computacion', '5w6', 'Descartes'), ('informatic', '5w6', 'Descartes'), ('ingenier', '5w6', 'Descartes'), ('electricidad', '5w6', 'Descartes'), ('banco', '5w6', 'Descartes'), ('bolsa', '5w6', 'Descartes'), ('geolog', '5w6', 'Descartes'), ('transporte', '6w5', 'Séneca'), ('farmacia', '6w5', 'Séneca'), ('insumos medicos', '6w5', 'Séneca'), ('contador', '6w5', 'Séneca'), ('administrador', '6w5', 'Séneca'), ('seguridad', '6w5', 'Séneca'), ('publicidad', '7w8', 'Epicuro'), ('marketing', '7w8', 'Epicuro'), ('deporte', '7w8', 'Epicuro'), ('profesor', '7w8', 'Epicuro'), ('capacitacion', '7w8', 'Epicuro'), ('construccion', '8w7', 'Sun Tzu'), ('maquinaria', '8w7', 'Sun Tzu'), ('autos', '8w7', 'Sun Tzu'), ('automotriz', '8w7', 'Sun Tzu'), ('tenis', '8w7', 'Sun Tzu'), ('futbol', '8w7', 'Sun Tzu'), ('paisajismo', '9w1', 'Lao Tsé'), ('aseo', '9w1', 'Lao Tsé'), ('limpieza', '9w1', 'Lao Tsé')]


def normalizar(texto):
    if pd.isna(texto):
        return ""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = texto.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def contiene_palabra(texto, palabra):
    return re.search(r"(?<![a-z0-9])" + re.escape(palabra) + r"(?![a-z0-9])", texto) is not None


def detectar_separador(ruta):
    with open(ruta, "r", encoding="utf-8-sig", errors="replace") as fh:
        for linea in fh:
            if linea.strip():
                if "|" in linea:
                    return "|"
                if "\t" in linea:
                    return "\t"
                if "," in linea:
                    return ","
                break
    raise ValueError(f"No se pudo detectar el separador en {ruta}")


def cargar_datos():
    if RUTA_CSV.is_file():
        df = pd.read_csv(RUTA_CSV, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    elif RUTA_TXT.is_file():
        df = pd.read_csv(
            RUTA_TXT,
            encoding="utf-8-sig",
            dtype=str,
            sep=detectar_separador(RUTA_TXT),
            keep_default_na=False,
        )
    else:
        raise FileNotFoundError(
            f"No existe {RUTA_CSV} ni {RUTA_TXT}. Se requiere uno de los dos archivos de entrada."
        )
    df.columns = [str(columna).strip() for columna in df.columns]
    requeridas = {"N°", "Nombre", "Eneatipo", "Info_clave", "Rubro"}
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas obligatorias en la entrada: {sorted(faltantes)}")
    return df


def clasificar(info_clave, rubro):
    info = normalizar(info_clave)
    puntajes = {}
    for eneatipo, (_, reglas) in MANUAL_VENTA.items():
        puntajes[eneatipo] = sum(peso for patron, peso in reglas if re.search(patron, info))

    maximo = max(puntajes.values())
    if maximo > 0:
        for eneatipo in MANUAL_VENTA:
            if puntajes[eneatipo] == maximo:
                return eneatipo, MANUAL_VENTA[eneatipo][0]

    for clave, eneatipo, arquetipo in REGLAS_INFO_CLAVE:
        if contiene_palabra(info, clave):
            return eneatipo, arquetipo

    rubro_norm = normalizar(rubro)
    for clave, eneatipo, arquetipo in REGLAS_RUBRO:
        if contiene_palabra(rubro_norm, clave):
            return eneatipo, arquetipo

    return "9w1", "Lao Tsé"


def main():
    df = cargar_datos()
    pendientes = df[df["Eneatipo"].astype(str).str.strip() == "?"].copy()
    if pendientes.empty:
        raise ValueError("No se encontraron filas con Eneatipo '?' para clasificar.")

    resultados = pendientes.apply(lambda fila: clasificar(fila["Info_clave"], fila["Rubro"]), axis=1)
    pendientes["Eneatipo"] = [resultado[0] for resultado in resultados]
    pendientes["Arquetipo"] = [resultado[1] for resultado in resultados]

    salida = pendientes[["N°", "Nombre", "Eneatipo", "Arquetipo"]].copy()
    numeros = pd.to_numeric(salida["N°"], errors="coerce")
    if numeros.isna().any():
        raise ValueError("Existen valores no numericos en la columna N°.")
    salida["N°"] = numeros.astype("Int64")

    if salida[["Eneatipo", "Arquetipo"]].isna().any().any():
        raise ValueError("La clasificacion genero valores nulos.")
    if (salida[["Eneatipo", "Arquetipo"]].astype(str).apply(lambda col: col.str.strip() == "").any().any()):
        raise ValueError("La clasificacion genero valores vacios.")
    if not set(salida["Eneatipo"]).issubset(set(MANUAL_VENTA)):
        raise ValueError("La clasificacion genero eneatipos fuera del manual de venta.")

    salida.to_csv(RUTA_SALIDA, index=False, encoding="utf-8-sig")

    print(f"Total procesado: {len(salida)}")
    print("Desglose por Eneatipo:")
    for eneatipo, cantidad in salida["Eneatipo"].value_counts().sort_index().items():
        print(f"  {eneatipo}: {cantidad}")
    print(f"Archivo generado: {RUTA_SALIDA}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
