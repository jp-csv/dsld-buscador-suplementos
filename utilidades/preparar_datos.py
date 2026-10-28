#!/usr/bin/env python3
"""
preparar_datos.py - Genera los archivos Parquet que usa la app de Streamlit (toda la base del DSLD).

Uso:
    python utilidades/preparar_datos.py CARPETA_CSV DSLD_JSON_EXTRA.csv [CARPETA_SALIDA]

(desde la raíz del repositorio)

CARPETA_CSV            carpeta con los CSV descomprimidos de la descarga completa del DSLD
DSLD_JSON_EXTRA.csv    archivo generado por utilidades/dsld_extract_json.py (atributos de etiqueta)
CARPETA_SALIDA         por defecto app/datos

Genera:
    etiquetas.parquet     una fila por etiqueta (todos los tipos de producto)
    ingredientes.parquet  una fila por ingrediente declarado (sin las filas de información nutrimental)
    atributos.parquet     una fila por etiqueta y atributo (Vegan, Organic, Gluten Free...)
"""
import glob
import os
import re
import sys

import numpy as np
import pandas as pd

CARGA_MASIVA = ["TerraVita Premium Collection", "TerraVita", "Herbal Terra", "Hawaii Pharm"]
FORMA_ES = {
    "Capsule": "Cápsula", "Liquid": "Líquido", "Powder": "Polvo", "Tablet or Pill": "Tableta o pastilla",
    "Softgel Capsule": "Cápsula blanda", "Gummy or Jelly": "Gomita o jalea",
    "Other (e.g. tea bag)": "Otra (p. ej., té)", "Lozenge": "Pastilla para chupar",
    "Unknown": "Desconocida", "Bar": "Barra",
}
TIPO_ES = {
    "Botanical": "Botánico",
    "Botanical with Nutrients": "Botánico con nutrientes",
    "Vitamin": "Vitamina",
    "Mineral": "Mineral",
    "Multi-Vitamin and Mineral (MVM)": "Multivitamínico y mineral",
    "Single Vitamin and Mineral": "Vitamina y mineral (individual)",
    "Amino acid/Protein": "Aminoácido o proteína",
    "Fat/Fatty Acid": "Grasa o ácido graso",
    "Fiber and Other Nutrients": "Fibra y otros nutrientes",
    "Non-Nutrient/Non-Botanical": "Otro no nutriente (no botánico)",
    "Other Combinations": "Otras combinaciones",
}

# Filas de la tabla de información nutrimental (no son ingredientes del suplemento).
NUTRIMENTAL = {
    "calories", "total calories", "calories from fat", "energy", "total fat", "saturated fat", "trans fat",
    "polyunsaturated fat", "monounsaturated fat", "fat", "cholesterol", "total carbohydrates",
    "total carbohydrate", "carbohydrates", "carbohydrate", "other carbohydrates", "sugar", "sugars",
    "total sugars", "added sugars", "includes added sugars",
}

# Ruido que se quita del nombre. En ingredientes botánicos se quita todo; en el resto se conservan
# palabras que sí identifican al ingrediente (fish OIL, krill OIL, juice, extract...).
RUIDO_BASE = (r"organic|organically grown|certified|wildcrafted|raw|dried|dry|fresh|powdered|powder|"
              r"standardized|concentrate|and|from")
RUIDO_BOTANICO = (RUIDO_BASE + r"|extract|extracts|whole|herb|herbs|root|roots|leaf|leaves|flower|flowers|"
                  r"seed|seeds|bark|fruit|berry|aerial parts?|rhizome|bulb|stem|juice|oil|tincture")
RE_BASE = re.compile(r"\b(" + RUIDO_BASE + r")\b")
RE_BOT = re.compile(r"\b(" + RUIDO_BOTANICO + r")\b")

# Vitaminas y nutrientes con varios nombres: se agrupan bajo un solo nombre (se aplica al nombre ya limpio).
SINONIMOS = [
    (r"vitamin a|retinol|retinyl.*|vitamin a palmitate", "vitamin a (retinol)"),
    (r"vitamin c|ascorb.*|calcium ascorbate|sodium ascorbate", "vitamin c (ascorbic acid)"),
    (r"vitamin d\d?|vitamin d-\d|cholecalciferol|ergocalciferol", "vitamin d (cholecalciferol)"),
    (r"vitamin e|(d|dl|d-alpha|dl-alpha|alpha)?[- ]?tocopher.*|mixed tocopherols", "vitamin e (tocopherol)"),
    (r"vitamin k\d?|vitamin k-\d|menaquinone.*|phylloquinone", "vitamin k"),
    (r"vitamin b-?1|thiamin|thiamine.*", "thiamin (vitamin b1)"),
    (r"vitamin b-?2|riboflavin.*", "riboflavin (vitamin b2)"),
    (r"vitamin b-?3|niacin|niacinamide|nicotinamide|inositol hexanicotinate", "niacin (vitamin b3)"),
    (r"vitamin b-?5|pantothenic acid|calcium pantothenate|d-calcium pantothenate", "pantothenic acid (vitamin b5)"),
    (r"vitamin b-?6|pyridox.*", "vitamin b6 (pyridoxine)"),
    (r"vitamin b-?7|biotin", "biotin (vitamin b7)"),
    (r"vitamin b-?9|folate|folic acid|l-?methylfolate|methylfolate|5-mthf|quatrefolic", "folate (vitamin b9)"),
    (r"vitamin b-?12|cobalamin|cyanocobalamin|methylcobalamin|hydroxocobalamin", "vitamin b12 (cobalamin)"),
]
SINONIMOS = [(re.compile(r"^(" + p + r")$"), canon) for p, canon in SINONIMOS]

MASA_A_MCG = {"mg": 1000.0, "Gram(s)": 1e6, "g": 1e6, "grams": 1e6, "mcg": 1.0, "ug": 1.0, "ng": 0.001}
UNIDAD_ALIAS = {
    "UI": "IU", "mg alpha-TE": "mg α-TE", "mg {alpha}-TE": "mg α-TE", "mg AT": "mg α-TE", "mg a-tocopherol": "mg α-TE",
    "mcg RE": "mcg RAE", "mg DFE": "mcg DFE", "{Calories}": "Calorie(s)", "Kcal": "Calorie(s)", "Kcal(s)": "Calorie(s)",
    "Calories": "Calorie(s)", "{microorganisms}": "CFU", "{Organisms}": "CFU", "Organism(s)": "CFU",
    "Viable Cell(s)": "CFU", "Cell(s)": "CFU",
}


def limpiar(nombre, categoria=""):
    s = nombre.lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9\s'-]", " ", s)
    s = (RE_BOT if categoria == "botanical" else RE_BASE).sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" -")
    if not s:
        return None
    for patron, canon in SINONIMOS:
        if patron.match(s):
            return canon
    return s


def cargar(carpeta, prefijo, columnas=None):
    archivos = sorted(glob.glob(os.path.join(carpeta, f"{prefijo}_*.csv")))
    if not archivos:
        sys.exit(f"No se encontraron {prefijo}_*.csv en {carpeta}")
    return pd.concat((pd.read_csv(f, dtype=str, keep_default_na=False, usecols=columnas) for f in archivos),
                     ignore_index=True)


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    carpeta, extra_csv = sys.argv[1], sys.argv[2]
    salida = sys.argv[3] if len(sys.argv) == 4 else os.path.join("app", "datos")
    os.makedirs(salida, exist_ok=True)
    quitar_codigo = lambda s: s.str.replace(r"\s*\[.*\]$", "", regex=True)

    # --- Etiquetas -------------------------------------------------------------------
    p = cargar(carpeta, "ProductOverview")
    tipo = quitar_codigo(p["Product Type [LanguaL]"])
    forma = quitar_codigo(p["Supplement Form [LanguaL]"])
    etiquetas = pd.DataFrame({
        "dsld_id": p["DSLD ID"].astype("int64"),
        "producto": p["Product Name"].str.strip(),
        "marca": p["Brand Name"].str.strip(),
        "tipo": tipo.map(TIPO_ES).fillna(tipo),
        "forma": forma.map(FORMA_ES).fillna(forma),
        "estatus": p["Market Status"].map({"On Market": "En mercado", "Off Market": "Descontinuado"}),
        "anio_entrada": p["Date Entered into DSLD"].str[:4].astype("int16"),
        "porcion": p["Serving Size"].str.strip(),
        "contenido": p["Net Contents"].str.strip(),
        "url": p["URL"],
    })
    etiquetas["carga_masiva"] = etiquetas["marca"].isin(CARGA_MASIVA)

    # --- Ingredientes ----------------------------------------------------------------
    cols = ["DSLD ID", "Ingredient", "DSLD Ingredient Categories", "Amount Per Serving", "Amount Per Serving Unit"]
    i = cargar(carpeta, "DietarySupplementFacts", cols)
    i["original"] = i["Ingredient"].str.strip()
    i = i[~i["original"].str.lower().isin(NUTRIMENTAL)]
    # Se limpia una sola vez cada par (nombre, categoría) distinto: mucho más rápido que fila por fila.
    pares = i[["original", "DSLD Ingredient Categories"]].drop_duplicates()
    pares["ingrediente"] = [limpiar(n, c) for n, c in zip(pares["original"], pares["DSLD Ingredient Categories"])]
    i = i.merge(pares, on=["original", "DSLD Ingredient Categories"], how="left").dropna(subset=["ingrediente"])

    unidad = i["Amount Per Serving Unit"].str.strip().replace(UNIDAD_ALIAS)
    cantidad = pd.to_numeric(i["Amount Per Serving"], errors="coerce")
    factor = unidad.map(MASA_A_MCG)
    es_masa = factor.notna()
    # valor: masa en mcg (así los números pequeños de vitaminas no se pierden); otras unidades, tal cual.
    valor = np.where(es_masa, cantidad * factor, cantidad)
    unidad_base = np.where(es_masa, "mcg", unidad.replace("", np.nan))
    ingredientes = pd.DataFrame({
        "dsld_id": i["DSLD ID"].astype("int64").to_numpy(),
        "original": i["original"].to_numpy(),
        "ingrediente": i["ingrediente"].to_numpy(),
        "categoria": i["DSLD Ingredient Categories"].to_numpy(),
        "valor": valor.astype("float32"),
        "unidad": unidad_base,
    })
    # Vitamina D: 1 IU = 0.025 mcg (equivalencia fija), así que se pasa a masa como el resto.
    # Las IU de vitaminas A y E dependen de la forma química, por eso se dejan en IU.
    vit_d = (ingredientes["ingrediente"] == "vitamin d (cholecalciferol)") & (ingredientes["unidad"] == "IU")
    ingredientes.loc[vit_d, "valor"] = ingredientes.loc[vit_d, "valor"] * 0.025
    ingredientes.loc[vit_d, "unidad"] = "mcg"
    ingredientes.loc[ingredientes["valor"].isna(), "unidad"] = np.nan
    ingredientes.loc[ingredientes["valor"] <= 0, ["valor", "unidad"]] = np.nan

    resumen = ingredientes.groupby("dsld_id").agg(
        n_ingredientes=("ingrediente", "size"),
        tiene_mezcla=("categoria", lambda s: (s == "blend").any()))
    etiquetas = etiquetas.merge(resumen, left_on="dsld_id", right_index=True, how="left")
    etiquetas["n_ingredientes"] = etiquetas["n_ingredientes"].fillna(0).astype("int16")
    etiquetas["tiene_mezcla"] = etiquetas["tiene_mezcla"].fillna(False).astype(bool)

    # --- Atributos (del JSON) --------------------------------------------------------
    x = pd.read_csv(extra_csv, dtype=str, keep_default_na=False, usecols=["dsld_id", "target_groups"])
    atributos = (x.assign(atributo=x["target_groups"].str.split(r" \| "))
                  .explode("atributo")[["dsld_id", "atributo"]])
    atributos = atributos[atributos["atributo"].str.strip() != ""]
    atributos["dsld_id"] = atributos["dsld_id"].astype("int64")
    atributos["atributo"] = atributos["atributo"].str.strip()
    atributos = atributos[atributos["dsld_id"].isin(etiquetas["dsld_id"])]

    # --- Guardar (categorías para que pese poco) ------------------------------------
    for df, cats in ((etiquetas, ["marca", "tipo", "forma", "estatus"]),
                     (ingredientes, ["original", "ingrediente", "categoria", "unidad"]),
                     (atributos, ["atributo"])):
        for c in cats:
            df[c] = df[c].astype("category")
    etiquetas.to_parquet(os.path.join(salida, "etiquetas.parquet"), index=False)
    ingredientes.to_parquet(os.path.join(salida, "ingredientes.parquet"), index=False, compression="zstd")
    atributos.to_parquet(os.path.join(salida, "atributos.parquet"), index=False)
    print(f"Etiquetas: {len(etiquetas):,} | ingredientes: {len(ingredientes):,} | atributos: {len(atributos):,}")
    print("Guardado en", salida)


if __name__ == "__main__":
    main()
