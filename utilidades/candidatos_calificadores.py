"""Paso 1 de la revisión sistemática de nombres: ¿qué palabras sobran con más frecuencia?

Para cada uno de los N ingredientes más comunes (los «ingredientes base») busca los demás nombres que contienen
TODAS sus palabras y alguna más ("ginkgo" -> "ginkgo biloba", "ginkgo phytosome"...). Cada palabra extra se cuenta
por en cuántos ingredientes base distintos aparece: las que aparecen en muchos (liquid, glycerite, anhydrous, hcl...)
son calificadores genéricos; las que aparecen en pocos suelen ser marcas, cepas o variedades.

La salida es una lista ordenada de candidatos. La decisión (quitar / normalizar / no fusionar) se toma a mano, con un
criterio escrito, y se registra en calificadores.csv. Este script no cambia nada por sí solo.

Uso:   python utilidades/candidatos_calificadores.py [CARPETA_DATOS] [N_BASE] [SALIDA.csv]
       (por defecto: app/datos, 1000, candidatos_calificadores.csv)
"""
import collections
import os
import re
import sys

import pandas as pd


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else os.path.join("app", "datos")
    n_base = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    salida = sys.argv[3] if len(sys.argv) > 3 else "candidatos_calificadores.csv"

    ing = pd.read_parquet(os.path.join(carpeta, "ingredientes.parquet"), columns=["dsld_id", "ingrediente"])
    ing["ingrediente"] = ing["ingrediente"].astype(str)
    etiquetas = ing.groupby("ingrediente")["dsld_id"].nunique()
    palabras = {n: frozenset(re.split(r"[\s\-+/,]+", n)) - {""} for n in etiquetas.index}
    por_palabra = collections.defaultdict(set)
    for n, ps in palabras.items():
        for p in ps:
            por_palabra[p].add(n)

    bases = etiquetas.sort_values(ascending=False).head(n_base).index
    cubre = etiquetas[bases].sum() / etiquetas.sum()
    print(f"Los {n_base} ingredientes más comunes concentran {cubre:.1%} de las etiquetas-ingrediente.")

    con_base, etq = collections.defaultdict(set), collections.Counter()
    for base in bases:
        pb = palabras[base]
        if not pb:
            continue
        rara = min(pb, key=lambda w: len(por_palabra[w]))  # se parte de la palabra menos frecuente: mucho más rápido
        for otro in por_palabra[rara]:
            po = palabras[otro]
            if otro != base and pb < po and len(po - pb) <= 2:
                for extra in po - pb:
                    con_base[extra].add(base)
                    etq[extra] += etiquetas[otro]
    out = pd.DataFrame([(p, len(b), etq[p]) for p, b in con_base.items()],
                       columns=["palabra", "ingredientes_base_con_la_palabra", "etiquetas_afectadas"])
    out = out.sort_values("ingredientes_base_con_la_palabra", ascending=False)
    out.to_csv(salida, index=False)
    print(f"{len(out):,} palabras candidatas guardadas en {salida}. Revisa las primeras ~300 y registra la decisión en "
          f"utilidades/calificadores.csv.")


if __name__ == "__main__":
    main()
