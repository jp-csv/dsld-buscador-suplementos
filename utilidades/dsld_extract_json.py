#!/usr/bin/env python3
"""
dsld_extract_json.py - Extrae del JSON completo del DSLD los campos que NO vienen en el CSV.

Uso:
    python dsld_extract_json.py RUTA_ENTRADA SALIDA.csv

RUTA_ENTRADA puede ser:
  - una carpeta con archivos .json y/o .zip (se recorre recursivamente), o
  - un archivo .zip con los .json adentro (se lee sin descomprimir).
Cada .json puede contener una etiqueta (objeto) o varias (lista de objetos).

Genera UNA fila por etiqueta con:
  dsld_id, off_market (0/1), entry_date, off_market_date, other_events,
  claims, target_groups, relaciones ("tipo:idRelacionado;..."), n_relaciones,
  net_qty, net_unit, serving_unit, serving_min_qty, serving_max_qty,
  daily_servings_min, daily_servings_max

Solo usa la libreria estandar de Python.
"""
import csv
import io
import json
import os
import sys
import zipfile
from collections import Counter

CAMPOS = [
    "dsld_id", "off_market", "entry_date", "off_market_date", "other_events",
    "claims", "target_groups", "relaciones", "n_relaciones",
    "net_qty", "net_unit", "serving_unit", "serving_min_qty", "serving_max_qty",
    "daily_servings_min", "daily_servings_max",
]

EVENTO_ENTRADA = "Date entered into DSLD"
EVENTO_SALIDA = "Off Market"


def unir(valores, sep=" | "):
    return sep.join(str(v).strip() for v in valores if v not in (None, ""))


def fila_de_etiqueta(j):
    eventos = {}
    otros = []
    for e in j.get("events") or []:
        tipo, fecha = e.get("type"), e.get("date")
        if tipo == EVENTO_ENTRADA:
            eventos["entry"] = fecha
        elif tipo == EVENTO_SALIDA:
            eventos["off"] = fecha
        else:
            otros.append(f"{tipo}:{fecha}")

    rel = j.get("labelRelationships") or []
    net = (j.get("netContents") or [{}])[0] or {}
    srv = (j.get("servingSizes") or [{}])[0] or {}

    return {
        "dsld_id": j.get("id"),
        "off_market": j.get("offMarket"),
        "entry_date": eventos.get("entry") or j.get("entryDate"),
        "off_market_date": eventos.get("off"),
        "other_events": ";".join(otros),
        "claims": unir(c.get("langualCodeDescription") for c in (j.get("claims") or [])),
        "target_groups": unir(j.get("targetGroups") or []),
        "relaciones": ";".join(f"{r.get('type')}:{r.get('labelId')}" for r in rel),
        "n_relaciones": len(rel),
        "net_qty": net.get("quantity"),
        "net_unit": net.get("unit"),
        "serving_unit": srv.get("unit"),
        "serving_min_qty": srv.get("minQuantity"),
        "serving_max_qty": srv.get("maxQuantity"),
        "daily_servings_min": srv.get("minDailyServings"),
        "daily_servings_max": srv.get("maxDailyServings"),
    }


def etiquetas_en(contenido):
    """Devuelve los objetos-etiqueta de un JSON (objeto o lista de objetos)."""
    datos = json.loads(contenido)
    if isinstance(datos, dict):
        return [datos]
    if isinstance(datos, list):
        return [d for d in datos if isinstance(d, dict)]
    return []


def es_json_valido(nombre):
    base = os.path.basename(nombre)
    return nombre.lower().endswith(".json") and not base.startswith(".") and "__MACOSX" not in nombre


def leer_zip(zf, origen):
    for nombre in zf.namelist():
        if es_json_valido(nombre):
            with zf.open(nombre) as fh:
                yield f"{origen}!{nombre}", fh.read()
        elif nombre.lower().endswith(".zip") and "__MACOSX" not in nombre:
            with zf.open(nombre) as fh:                 # zip dentro de zip
                interno = zipfile.ZipFile(io.BytesIO(fh.read()))
                yield from leer_zip(interno, f"{origen}!{nombre}")


def recorrer(ruta):
    if os.path.isfile(ruta) and ruta.lower().endswith(".zip"):
        with zipfile.ZipFile(ruta) as zf:
            yield from leer_zip(zf, os.path.basename(ruta))
        return
    for carpeta, _, nombres in os.walk(ruta):
        for n in sorted(nombres):
            ruta_n = os.path.join(carpeta, n)
            if n.lower().endswith(".zip") and not n.startswith("."):
                with zipfile.ZipFile(ruta_n) as zf:
                    yield from leer_zip(zf, n)
            elif es_json_valido(ruta_n):
                with open(ruta_n, "rb") as fh:
                    yield ruta_n, fh.read()


def extraer(entrada, salida):
    """Recorre ENTRADA (carpeta o .zip con los .json del DSLD) y escribe SALIDA (.csv)."""
    if not os.path.exists(entrada):
        raise FileNotFoundError(f"No existe: {entrada}")
    vistos, errores = set(), []
    eventos, n_archivos, n_etiquetas = Counter(), 0, 0
    with open(salida, "w", newline="", encoding="utf-8-sig") as out:
        w = csv.DictWriter(out, fieldnames=CAMPOS)
        w.writeheader()
        for origen, contenido in recorrer(entrada):
            n_archivos += 1
            try:
                for j in etiquetas_en(contenido):
                    fila = fila_de_etiqueta(j)
                    if fila["dsld_id"] in vistos:       # evita duplicados si hay partes repetidas
                        continue
                    vistos.add(fila["dsld_id"])
                    for e in j.get("events") or []:
                        eventos[e.get("type")] += 1
                    w.writerow(fila)
                    n_etiquetas += 1
            except Exception as exc:                    # un archivo raro no detiene el proceso
                errores.append((origen, repr(exc)))
            if n_archivos % 20000 == 0:
                print(f"  ... {n_archivos:,} archivos / {n_etiquetas:,} etiquetas", flush=True)

    print(f"\nArchivos leidos: {n_archivos:,} | etiquetas unicas: {n_etiquetas:,} | errores: {len(errores)}")
    print("Tipos de evento encontrados:", dict(eventos))
    for origen, exc in errores[:10]:
        print("  error:", origen, exc)
    print("Salida:", salida)
    return n_etiquetas


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    try:
        extraer(sys.argv[1], sys.argv[2])
    except FileNotFoundError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
